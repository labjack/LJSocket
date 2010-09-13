# SkyMoteCommandResponseService - Handles the command/reponse side of comms.
from twisted.internet.protocol import Protocol, ServerFactory
from twisted.internet import defer

import os
import struct

class SkyMoteCommandResponseProtocol(Protocol):
    # Twisted calls these functions
    def connectionMade(self):
        print "SkyMoteCommandResponseProtocol connectionMade: made connection"
        self.connectionNumber = self.factory.connectionNumber
        self.factory.connectionNumber += 1
        self.queuedJobs = list()
        if self.factory.inLockdown:
            self.locked = True
        else:
            self.locked = False
        self.factory.connections[self.connectionNumber] = self
        
    def connectionLost(self, reason):
        print "SkyMoteCommandResponseProtocol connectionLost: reason: %s" % str(reason)
        if self.factory.inLockdown and not self.locked:
            self.factory.unlockEveryone()
        self.factory.connections.pop(self.connectionNumber)
 
    def dataReceived(self, data):
        """
        Twisted calls this function when we received data
        TODO: Check for fragments
        """
        if self.locked:
            print "Locked connection got data. Stashing for later..."
            d = defer.Deferred()
            d.addCallback(self.responseReceived)
            self.queuedJobs.append([data, d])
            
            return True
        
        print "dataReceived: got data.  length: %d" % len(data)        
        print "dataReceived: ",
        print [ hex(ord(c)) for c in data ]
        
        if len(data.strip()) == 4:
            data = data.strip()
            print "Got special command:", data
            if data.lower() == "lock":
                # Prevent others from talking to this device
                self.factory.lockout(self.connectionNumber)
            elif data.lower() == "done":
                # Allow others to talk to the device
                self.factory.unlockEveryone()
        else:
            d = defer.Deferred()
            d.addCallback(self.responseReceived)
            
            #self.factory.exchanger.newPacketEvent.set()
            readBytes = self.factory.writeRead(data, d)
        
    def responseReceived(self, data):
        print "responseReceived: Got results:", data
        results = struct.pack("B" * len(data), *data)
        print "responseReceived: len of packet", len(results)
        print "type(self.transport)", type(self.transport), self.transport
        self.transport.writeSomeData(results)
        
    def closeConnection(self):
        print "Connection # %s closing connection." % (self.connectionNumber)
        os.close(self.transport.fileno())
        
        return True
        

class SkyMoteCommandResponseFactory(ServerFactory):
    protocol = SkyMoteCommandResponseProtocol
    def __init__(self, exchanger): 
        self.exchanger = exchanger
        self.connectionNumber = 0
        self.connections = dict()
        self.inLockdown = False
    
    def lockout(self, connectionNumber):
        # Locks everyone except for one
        print "Locking out everyone except ", connectionNumber
        self.inLockdown = True
        for n, c in self.connections.items():
            if n != connectionNumber:
                c.locked = True
        
    def unlockEveryone(self):
        for c in self.connections.values():
            c.locked = False
            while len(c.queuedJobs) != 0:
                j = c.queuedJobs.pop()
                self.writeRead(j[0], j[1])
        self.inLockdown = False
    
    def writeRead(self, writeMessage, resultDeferred):
        return self.exchanger.writeRead(writeMessage, resultDeferred)

    def clientConnectionLost(self, connector, reason):
        print "Lost connection: %s" % reason.getErrorMessage()