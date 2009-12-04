import LabJackPython
from RawDevice import RawDeviceFactory
from ModbusDevice import ModbusDeviceFactory
MODBUS_PORT  = 5020

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
        for prodID in PRODUCT_IDS:
            self.deviceCountsByType[prodID] = 0
        self.nextPort = 6001
        self.rawDeviceServices = dict()
        self.modbusService = None

    def scan(self):
        print "scanning"
        # Check everything we know about
        for serial, d in self.devices.items():
            if not LabJackPython.isHandleValid(d.handle):
                # We lost this device
                self.deviceCountsByType[d.devType] -= 1
                d.close()
                print "Deleting device", self.devices[serial]
                del self.devices[serial]
                del self.portBySerial[serial]
                self.serviceCollection.removeService(self.rawDeviceServices[serial])
                del self.rawDeviceServices[serial]

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
                    if len(self.devices) == 1:
                        # Set up the Modbus port for the first device
                        port = MODBUS_PORT
                        modbusFactory = ModbusDeviceFactory(self, d.serialNumber)
                        self.modbusService = internet.TCPServer(port, modbusFactory)
                        self.modbusService.setServiceParent(self.serviceCollection)
                    port = self.nextPort
                    self.portBySerial[d.serialNumber] = port
                    factory = RawDeviceFactory(self, d.serialNumber)
                    service = internet.TCPServer(port, factory)
                    service.setServiceParent(self.serviceCollection)
                    self.rawDeviceServices[d.serialNumber] = service
                    self.nextPort += 1

        returnLines = list()
        for serial, d in self.devices.items():
            line = DeviceLine(d.devType, self.portBySerial[serial], d.localId, d.serialNumber)
            returnLines.append(line)
        if self.modbusService is not None:
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
