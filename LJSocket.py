import LabJackPython
import skymote
from RawDevice import RawDeviceFactory
from ModbusDevice import ModbusDeviceFactory
from SkyMoteExchanger import SkyMoteExchanger

# The command Response port is for UD Family devices.
COMMAND_RESPONSE_STARTING_PORT = 6001

# The Modbus port is for Modbus commands. For any LabJack device that supports Modbus.
MODBUS_STARTING_PORT  = 5021

# The Spontaneous port is where spontaneous data from Skymotes will go.
SPONTANEOUS_STARTING_PORT = 7021

from twisted.internet import reactor
from twisted.application import internet
from twisted.internet import protocol
from twisted.protocols import basic

from collections import namedtuple
import struct

# 3 = U3
# 6 = U6
# 9 = UE9
PRODUCT_IDS = [3, 6, 9, 0x501]

DeviceLine = namedtuple('DeviceLine', 'devType crport modbusport spontport localId serialNumber')
# Override how namedtuple prints. Just join the fields with spaces
class DeviceLine(DeviceLine):
    def __repr__(self):
        return " ".join(str(i) for i in self)

class DeviceManager(object):
    def __init__(self, serviceCollection):
        self.serviceCollection = serviceCollection
        self.devices = dict()
        self.deviceCountsByType = dict()
        for prodID in PRODUCT_IDS:
            self.deviceCountsByType[prodID] = 0
        
        # Initialize ports
        self.nextCRPort = COMMAND_RESPONSE_STARTING_PORT
        self.nextModbusPort = MODBUS_STARTING_PORT
        self.nextSpontPort = SPONTANEOUS_STARTING_PORT
        
        self.rawDeviceServices = dict()
        self.modbusDeviceServices = dict()
        self.exchangers = dict()
        
        
        #self.tmpDict = {3: 0, 6: 0, 9: 0, 0x501: 1}
        
        reactor.addSystemEventTrigger('during', 'shutdown', self.shutdownExchangers)

    def scanSetupModbusService(self, d):
        print "setting self.modbusDeviceSerial =", d.serialNumber
        self.modbusDeviceSerial = d.serialNumber
        if self.modbusService is None:
            self.modbusFactory = ModbusDeviceFactory(self, self.modbusDeviceSerial)
            self.modbusService = internet.TCPServer(MODBUS_PORT, self.modbusFactory)
            self.modbusService.setServiceParent(self.serviceCollection)
        else:
            # We already have a Modbus service, just change what device serves
            self.modbusFactory = self.modbusDeviceSerial

    def scanExistingDevices(self):
        """Check everything we know about. If something is gone, remove it."""
        for serial, d in self.devices.items():
            print "Checking %s for a vaild handle." % serial
            if not LabJackPython.isHandleValid(d.handle):
                # We lost this device
                self.deviceCountsByType[d.devType] -= 1

                d.close()
                print "Deleting device", self.devices[serial]
                self.devices.pop(serial)
                if d.devType == 0x501:
                    ex = self.exchangers[d.serialNumber][0]
                    ex.shutdown(self.serviceCollection)
                    self.exchangers.pop(d.serialNumber)
                else:
                    self.serviceCollection.removeService(self.rawDeviceServices[serial])
                    self.rawDeviceServices.pop(serial)
                    
                    self.serviceCollection.removeService(self.modbusDeviceServices[serial])
                    self.modbusDeviceServices.pop(serial)

    def incrementPorts(self):
        self.nextCRPort += 1
        self.nextModbusPort += 1
        self.nextSpontPort += 1

    def _openSkymoteBridge(self, device):
        """ Opens any new bridges and starts up exchangers for them.
        """
        d = skymote.Bridge( autoOpen = False )
        d.loadGenericDevice(device)
        
        self.deviceCountsByType[0x501] += 1
        
        print "Opened d =", d
        d.modbusPortNum = self.nextModbusPort
        d.spontPortNum = self.nextSpontPort 
        self.devices[d.serialNumber] = d
        
        se = SkyMoteExchanger(d, self.nextModbusPort, self.nextSpontPort, self.serviceCollection, self.scanExistingDevices)
        
        self.exchangers[d.serialNumber] = (se, self.nextModbusPort, self.nextSpontPort)
        
        self.incrementPorts()
                
    
    def scan(self):
        print "scanning"
        
        self.scanExistingDevices()
        
        devices = LabJackPython.openAllLabJacks()

        for device in devices:
            prodID = device.devType
            
            if prodID == 0x501:
                self._openSkymoteBridge(device)
                continue
            
            device._registerAtExitClose()
            self.deviceCountsByType[prodID] += 1
            print "Opened d =", device
            self.devices[device.serialNumber] = device
            
            # Set up the Modbus port
            device.modbusPortNum = self.nextModbusPort
            
            modbusFactory = ModbusDeviceFactory(self, device.serialNumber)
            modbusService = internet.TCPServer(self.nextModbusPort, modbusFactory)
            modbusService.setServiceParent(self.serviceCollection)
            
            self.modbusDeviceServices[device.serialNumber] = modbusService
            
            # Set up C/R port
            port = self.nextCRPort
            device.crPortNum = port
            factory = RawDeviceFactory(self, device.serialNumber)
            service = internet.TCPServer(port, factory)
            service.setServiceParent(self.serviceCollection)
            self.rawDeviceServices[device.serialNumber] = service
            
            self.incrementPorts()

        return self.buildScanResponse()


    def buildScanResponse(self):
        ''' Builds a list of lines about each device LJSocket knows about. '''
        returnLines = list()
        for serial, d in self.devices.items():
            if d.devType == 0x501:
                line = DeviceLine(d.devType, 'x', d.modbusPortNum, d.spontPortNum, d.localId, d.serialNumber)
            else:
                line = DeviceLine(d.devType, d.crPortNum, d.modbusPortNum, 'x', d.localId, d.serialNumber)
            returnLines.append(line)
        
        return returnLines

    def writeRead(self, serial, writeBytes):
        """
            Write writeBytes to LabJack with given serial, read and 
            return the response.
        """
        print "writeRead: serial: %s" % serial
        if serial not in self.devices:
            print "writeRead: no device with serial %s" % serial
            return ""
        print "writeRead: writing %d bytes" % len(writeBytes)
        d = self.devices[serial]
        writeList = [ ord(b) for b in writeBytes ]
        readList = d._writeRead(writeList, 64, [], False, False, False)
        readLen = len(readList)
        readBytes = struct.pack('>' + 'B'*readLen, *readList)
        print "writeRead: read %d bytes" % len(readBytes)
        print "writeRead:", [ ord(b) for b in readBytes ]
        
        return readBytes
        
    def shutdownExchangers(self):
        print "Shutting down exchangers"
        for ex, p1, p2 in self.exchangers.values():
            ex.shutdown()
        print "Done"
        return True

class SocketServiceProtocol(basic.LineReceiver):
    def lineReceived(self, line):
        if "scan" == line.lower():
            deviceLines = self.factory.manager.scan()
            numDevices = len(deviceLines)
            self.sendLine("OK " + str(numDevices))
            for line in deviceLines:
                self.sendLine(str(line))
            self.transport.loseConnection()

# Assigned a manager attribute in socketService
class SocketServiceFactory(protocol.ServerFactory):
    protocol = SocketServiceProtocol
