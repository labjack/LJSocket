# SkyMoteCommandResponseService - Handles the command/reponse side of comms.
from twisted.internet.protocol import Protocol, ServerFactory
from twisted.internet import defer
from twisted.protocols import basic

import os
import struct
import json

class SkyMoteSpontaneousProtocol(basic.LineReceiver):
    # Twisted calls these functions
    def connectionMade(self):
        print "SkyMoteSpontaneousProtocol connectionMade: made connection"
        self.outputFormat = "raw"
        self.connectionNumber = self.factory.connectionNumber
        self.factory.connections[self.connectionNumber] = self
        self.factory.connectionNumber += 1
        
    def connectionLost(self, reason):
        print "SkyMoteSpontaneousProtocol connectionLost: reason: %s" % str(reason)
        self.factory.connections.pop(self.connectionNumber)
    
    
    def lineReceived(self, line):
        print "Recieved Line!", line
        line = line.strip()
        if "csv" == line.lower():
            self.outputFormat = "csv"
            self.sendLine("OK CSV")
        elif "json" == line.lower():
            self.outputFormat = "json"
            self.sendLine("OK JSON")
        else:
            self.outputFormat = "raw"
            self.sendLine("OK RAW")
    
    def sendData(self, data):
        #print "Sending Spontaneous Data: ", data
        results = struct.pack("B" * len(data), *data)
        if self.outputFormat == "raw":
            self.transport.writeSomeData(results)
            return True
        else:
            localId = ord(results[6])     
            if self.outputFormat == "csv":
                print "sending csv"
                results = list(struct.unpack(">"+"f"*7, results[9:37]))
                results.insert(0, localId)
                #self.sendLine(", ".join([ str(i) for i in results ]))
                self.transport.writeSomeData(", ".join([ str(i) for i in results ]) + "\r\n")
            elif self.outputFormat == "json":
                rxLqi, txLqi, battery, temp, light, bump, sound = struct.unpack(">"+"f"*7, results[9:37])
                
                results = dict()
                results['unitId'] = localId
                results['RxLQI'] = rxLqi
                results['TxLQI'] = txLqi
                results['Battery'] = battery
                results['Temp'] = temp
                results['Light'] = light
                results['Bump'] = bump
                results['Sound'] = sound
                self.transport.writeSomeData(json.dumps(results) + "\r\n")
                
            return True
            
                
        
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