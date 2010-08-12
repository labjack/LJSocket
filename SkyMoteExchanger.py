# SkyMote Exchanger - A class to handle reading data from the bridge and sending
# it to the correct place.
from Queue import Queue
import Modbus

from twisted.internet import reactor
from twisted.application import internet

from SkyMoteCommandResponseService import SkyMoteCommandResponseFactory
from SkyMoteSpontaneousDataService import SkyMoteSpontaneousFactory

from time import sleep

class SkyMoteExchanger(object):
    def __init__(self, device, commandResponsePort, spontaneousPort, serviceCollection, deviceLostFnx ):
        print "Starting up C/R port on %s and Spontaneous %s" % (commandResponsePort, spontaneousPort)
        
        self.device = device
        
        self.commandQueue = Queue(-1)
        self.sentCommands = dict() # Holds the deferred for a transaction
        
        self.serviceCollection = serviceCollection
        
        factory = SkyMoteCommandResponseFactory(self)
        self.commandResponseService = internet.TCPServer(commandResponsePort, factory)
        self.commandResponseService.setServiceParent(serviceCollection)
        
        factory = SkyMoteSpontaneousFactory()
        self.spontaneousService = internet.TCPServer(spontaneousPort, factory)
        self.spontaneousService.setServiceParent(serviceCollection)
        
        self.deviceLost = deviceLostFnx
        
        self.running = True
        
        reactor.callInThread(self.loopingRead)
    
    def writeRead(self, data, resultDeferred):
        self.commandQueue.put_nowait( (data, resultDeferred) )
    
    def writeCommandsToDevice(self):
        try:
            while True:
                print "writeCommandsToDevice: Waiting for a command to write."
                command, resultDefered = self.commandQueue.get_nowait()
                print "writeCommandsToDevice: Got a command to write. %s" % repr(command)
                transId = Modbus.getTransactionId(command)
                self.sentCommands[str(transId)] = resultDefered
                
                command = [ ord(c) for c in command ]
                self.device.write(command, checksum = False, modbus = True)
        except Exception, e:
            print type(e), e
            print "writeCommandsToDevice: No more commands to write."
    
    def shutdown(self, serviceCollection = None):
        # Shutdown all open connections
        for connection in self.commandResponseService.args[1].connections.values():
            connection.closeConnection()
            
        for connection in self.spontaneousService.args[1].connections.values():
            connection.closeConnection()
        
        if serviceCollection is not None:
            serviceCollection.removeService(self.commandResponseService)
            serviceCollection.removeService(self.spontaneousService)
        
        self.running = False
    
    def sendSpontaneousData(self, data):
        for connection in self.spontaneousService.args[1].connections.values():
            connection.sendData(data)
        
    
    def loopingRead(self):
        while self.running:
            if not self.commandQueue.empty():
                self.writeCommandsToDevice()
            
            try:
                #print "Start read."
                packet = self.device.read(64)
                #print "Read returned. Len = %s" % len(packet)
                
                if len(packet) != 0:
                    protoId = Modbus.getProtocolId(packet)
                    if protoId == 0:
                        transId = Modbus.getTransactionId(packet)
                        print "---------------------------------   Calling callback for transId = %s" % transId
                        self.sentCommands[str(transId)].callback(packet)
                        self.sentCommands.pop(str(transId))
                        sleep(0.1)
                        
                    else:
                        #print "Got spontaneous data!"
                        self.sendSpontaneousData(packet)

            except Exception, e:
                if str(e).endswith('-7'):
                    #print "Read timed out."
                    pass
                else:
                    print type(e), e
                    self.deviceLost()
        
        self.device.close()
        print "Shutting down read loop."
            