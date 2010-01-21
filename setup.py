from distutils.core import setup
import py2exe

setup(
    service=["ljsocketService"],
    options={
        "py2exe":{
            "bundle_files" : 1,
            "excludes" : ["Tkinter", "Tkconstants", "tcl"],
        }
    },
    zipfile = None
) 
