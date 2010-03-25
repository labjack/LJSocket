# Handles starting and running LJSocket as a Windows service

# Service Utilities
import win32serviceutil
import win32service
import win32event

# Twisted imports
from twisted.internet.protocol import Protocol, Factory
from twisted.internet import reactor

DEFAULT_PORT = 6000

class WindowsService(win32serviceutil.ServiceFramework):
    _svc_name_ = "LJSocket"
    _svc_display_name_ = "LJSocket Win32 Service"

    def __init__(self, args):
        win32serviceutil.ServiceFramework.__init__(self, args)
        self.hWaitStop = win32event.CreateEvent(None, 0, 0, None)

    def SvcStop(self):
        self.ReportServiceStatus(win32service.SERVICE_STOP_PENDING)
        win32event.SetEvent(self.hWaitStop)

    def SvcDoRun(self):
        import servicemanager
        from LJSocket import SocketServiceFactory, DeviceManager
        import ljsocketServiceTac
        
        self.CheckForQuit()
        
        try:
            f = file("C:\LJSocket.log", 'w')
        except:
            f = file("LJSocket.log", 'w')

        from twisted.python.log import startLogging
        from twisted.application.app import startApplication
        from twisted.internet import reactor        
        startLogging(f)
        startApplication(ljsocketServiceTac.application, 0)
        #reactor.run()

        reactor.run(installSignalHandlers=0)


    def CheckForQuit(self):
        retval = win32event.WaitForSingleObject(self.hWaitStop, 10)
        if not retval == win32event.WAIT_TIMEOUT:
            # Received Quit from Win32
            reactor.stop()

        reactor.callLater(1.0, self.CheckForQuit)

if __name__=='__main__':
    win32serviceutil.HandleCommandLine(WindowsService)