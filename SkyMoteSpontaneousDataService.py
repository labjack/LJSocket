# SkyMoteCommandResponseService - Handles the command/reponse side of comms.
from twisted.internet.protocol import Protocol, ServerFactory
from twisted.internet import defer
from twisted.protocols import basic

import os
import struct
import json
from datetime import datetime

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
            transId = struct.unpack(">H", results[0:2])[0]
            report = list(struct.unpack(">HBBfHH"+"f"*8, results[9:53]))  
            if self.outputFormat == "csv":
                print "sending csv"
                results = list()
                results.append(str(datetime.now()))
                results.append(localId)
                results.append(transId)
                results.append(report[6]) # Temp
                results.append(report[7]) # Light
                results.append(report[4]) # Bump
                results.append(report[1]) # RxLQI
                results.append(report[2]) # TxLQI
                results.append(report[3]) # Battery
                #results.append(report[11]) # Sound
                
                self.transport.writeSomeData(",".join([ str(i) for i in results ]) + "\r\n")
            elif self.outputFormat == "json":
                results = dict()
                results['timestamp'] = str(datetime.now())
                results['unitId'] = localId
                results['transId'] = transId
                results['RxLQI'] = report[1]
                results['TxLQI'] = report[2]
                results['Battery'] = report[3]
                results['Temp'] = report[6]
                results['Light'] = report[7]
                results['Bump'] = report[4]
                #results['Sound'] = report[11]
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