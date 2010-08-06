# SkyMoteCommandResponseService - Handles the command/reponse side of comms.
from twisted.internet.protocol import Protocol, ServerFactory
from twisted.internet import defer

import os
import struct

class SkyMoteSpontaneousProtocol(Protocol):
    # Twisted calls these functions
    def connectionMade(self):
        print "SkyMoteSpontaneousProtocol connectionMade: made connection"
        self.connectionNumber = self.factory.connectionNumber
        self.factory.connections[self.connectionNumber] = self
        self.factory.connectionNumber += 1
        
    def connectionLost(self, reason):
        print "SkyMoteSpontaneousProtocol connectionLost: reason: %s" % str(reason)
        self.factory.connections.pop(self.connectionNumber)
        
    def sendData(self, data):
        print "Sending Spontaneous Data: ", data
        results = struct.pack("B" * len(data), *data)
        print "Sending Spontaneous Data: len of packet", len(results)
        self.transport.writeSomeData(results)
        
    def closeConnection(self):
        print "Connection # %s closing connection." % (self.connectionNumber)
        os.close(self.transport.fileno())
        
        return True

class SkyMoteSpontaneousFactory(ServerFactory):
    protocol = SkyMoteSpontaneousProtocol
    def __init__(self):
        self.connectionNumber = 0
        self.connections = dict()

    def clientConnectionLost(self, connector, reason):
        print "Lost connection: %s" % reason.getErrorMessage()