import LabJackPython
import skymote
from RawDevice import RawDeviceFactory
from ModbusDevice import ModbusDeviceFactory
from SkyMoteExchanger import SkyMoteExchanger
MODBUS_PORT  = 5020

from twisted.internet import reactor
from twisted.application import internet
from twisted.internet import protocol
from twisted.protocols import basic

from collections import namedtuple
import struct

# 3 = U3
# 6 = U6
# 9 = UE9
PRODUCT_IDS = [3, 6, 9]

DeviceLine = namedtuple('DeviceLine', 'devType port localId serialNumber')
# Override how namedtuple prints. Just join the fields with spaces
class DeviceLine(DeviceLine):
    def __repr__(self):
        return " ".join(str(i) for i in self)

class DeviceManager(object):
    def __init__(self, serviceCollection):
        self.serviceCollection = serviceCollection
        self.devices = dict()
        self.deviceCountsByType = dict()
        self.portBySerial = dict()
        self.deviceCountsByType[0x501] = 0
        for prodID in PRODUCT_IDS:
            self.deviceCountsByType[prodID] = 0
        self.nextPort = 6001
        self.rawDeviceServices = dict()
        self.exchangers = dict()
        self.modbusFactory = None
        self.modbusService = None
        self.modbusDeviceSerial = None
        
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
                # If this was the device we advertised over Modbus, set the
                # modbusDeviceSerial to None so that we can offer another 
                # device over Modbus
                if d.serialNumber == self.modbusDeviceSerial:
                    self.modbusDeviceSerial = None
                d.close()
                print "Deleting device", self.devices[serial]
                del self.devices[serial]
                del self.portBySerial[serial]
                if d.devType == 0x501:
                    ex = self.exchangers[d.serialNumber][0]
                    ex.shutdown(self.serviceCollection)
                    self.exchangers.pop(d.serialNumber)
                else:
                    self.serviceCollection.removeService(self.rawDeviceServices[serial])
                    del self.rawDeviceServices[serial]

    def scan(self):
        print "scanning"
        
        self.scanExistingDevices()

        # To skymote bridges first, because they are special
        devCount = LabJackPython.deviceCount(0x501)
        if devCount != self.deviceCountsByType[0x501]:
            for i in range(self.deviceCountsByType[0x501] + 1, devCount + 1):
                d = skymote.Bridge( LJSocket = None, firstFound = False, devNumber = i )
                self.deviceCountsByType[0x501] += 1
                
                print "Opened d =", d
                #self.devices[d.serialNumber] = d
                
                # Set up the Modbus port for the first found device
                port = self.nextPort
                
                d.localId = port+1 
                self.devices[d.serialNumber] = d
                
                self.modbusDeviceSerial = d.serialNumber
                
                se = SkyMoteExchanger(d, port, port+1, self.serviceCollection)
                
                self.portBySerial[d.serialNumber] = port
                self.exchangers[d.serialNumber] = (se, port, port+1)
                
                self.nextPort += 2
             

        for prodID in PRODUCT_IDS:
            devCount = LabJackPython.deviceCount(prodID)
            print "prodID : devCount = ", prodID, ":", devCount
            if devCount != self.deviceCountsByType[prodID]:
                extraDevs = devCount - self.deviceCountsByType[prodID]
                if extraDevs <= 0:
                    print extraDevs, "is negative or zero. Error."
                    break
                for i in range(self.deviceCountsByType[prodID] + 1, devCount + 1):
                    d = LabJackPython.Device(None,  devType = prodID)
                    d.open(prodID, devNumber = i)
                    self.deviceCountsByType[prodID] += 1
                    print "Opened d =", d
                    self.devices[d.serialNumber] = d
                    # Set up the Modbus port for the first found device
                    if self.modbusDeviceSerial is None:
                        self.scanSetupModbusService(d)
                    port = self.nextPort
                    self.portBySerial[d.serialNumber] = port
                    factory = RawDeviceFactory(self, d.serialNumber)
                    service = internet.TCPServer(port, factory)
                    service.setServiceParent(self.serviceCollection)
                    self.rawDeviceServices[d.serialNumber] = service
                    self.nextPort += 1

        # If there are devices left, turn off the Modbus service
        if len(self.devices) == 0:
            if self.modbusService:
                self.serviceCollection.removeService(self.modbusService)
                self.modbusDeviceSerial = self.modbusService = self.modbusFactory = None
        else:
            if self.modbusDeviceSerial is None:
                # We have devices plugged in, but we lost our Modbus device
                # Pick the first one and make it available.
                self.scanSetupModbusService(self.devices.values()[0])

        return self.buildScanResponse()


    def buildScanResponse(self):
        ''' Builds a list of lines about each device LJSocket knows about. '''
        returnLines = list()
        for serial, d in self.devices.items():
            line = DeviceLine(d.devType, self.portBySerial[serial], d.localId, d.serialNumber)
            returnLines.append(line)
        if self.modbusDeviceSerial is not None:
            d = self.devices[self.modbusDeviceSerial]
            line = DeviceLine(d.devType, MODBUS_PORT, d.localId, d.serialNumber)
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
