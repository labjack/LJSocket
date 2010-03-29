# SkyMoteCommandResponseService - Handles the command/reponse side of comms.
from twisted.internet.protocol import Protocol, ServerFactory
from twisted.internet import defer

import struct

class SkyMoteCommandResponseProtocol(Protocol):
    # Twisted calls these functions
    def connectionMade(self):
        print "SkyMoteCommandResponseProtocol connectionMade: made connection"
        
    def connectionLost(self, reason):
        print "SkyMoteCommandResponseProtocol connectionLost: reason: %s" % str(reason)
 
    def dataReceived(self, data):
        """
        Twisted calls this function when we received data
        TODO: Check for fragments
        """
        print "dataReceived: got data.  length: %d" % len(data)        
        print "dataReceived: ",
        print [ hex(ord(c)) for c in data ]
        
        d = defer.Deferred()
        d.addCallback(self.responseReceived)
        
        readBytes = self.factory.writeRead(data, d)
        
    def responseReceived(self, data):
        print "responseReceived: Got results:", data
        results = struct.pack("B" * len(data), *data)
        print "responseReceived: len of packet", len(results)
        print "type(self.transport)", type(self.transport), self.transport
        self.transport.writeSomeData(results)
        

class SkyMoteCommandResponseFactory(ServerFactory):
    protocol = SkyMoteCommandResponseProtocol
    def __init__(self, exchanger): 
        self.exchanger = exchanger
        
    def writeRead(self, writeMessage, resultDeferred):
        return self.exchanger.writeRead(writeMessage, resultDeferred)

    def clientConnectionLost(self, connector, reason):
        print "Lost connection: %s" % reason.getErrorMessage()