from twisted.application import service, internet

from LJSocket import SocketServiceFactory, DeviceManager

DEFAULT_PORT = 6000

application = service.Application("SocketService") 
serviceCollection = service.IServiceCollection(application)
manager = DeviceManager(serviceCollection)
ssf = SocketServiceFactory()
ssf.manager = manager

internet.TCPServer(DEFAULT_PORT, ssf).setServiceParent(serviceCollection)
