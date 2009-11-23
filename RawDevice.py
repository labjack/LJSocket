from twisted.internet.protocol import Protocol, ServerFactory

class RawDeviceProtocol(Protocol):
 
    # Twisted calls these functions
    def connectionMade(self):
        print "connectionMade: made connection"
        #self.transport.setTcpKeepAlive(True)
        
    def connectionLost(self, reason):
        print "connectionLost: reason: %s" % str(reason)
 
    def dataReceived(self, data):
        """
        Twisted calls this function when we received data
        TODO: Check for fragments
        """
        print "dataReceived: got data.  length: %d" % len(data)        
        print "dataReceived: ",
        print [ hex(ord(c)) for c in data ]
        readBytes = self.factory.writeRead(data)
        self.transport.write(readBytes)


class RawDeviceFactory(ServerFactory):
    protocol = RawDeviceProtocol
    def __init__(self, deviceManager, serial): 
        self.deviceManager = deviceManager
        self.serial = serial
        
    def writeRead(self, writeMessage):
        return self.deviceManager.writeRead(self.serial, writeMessage)

    def clientConnectionLost(self, connector, reason):
        print "Lost connection: %s" % reason.getErrorMessage()
