# ESPER Waveform and Variable viewer

from __future__ import print_function
from builtins import str as text

import os
import sys
import argparse
import cmd
import time
import getpass
import array
import platform
import configparser
import zmq
import socket
import struct
import re
import zlib
import pickle
import queue
import pyqtgraph as pg
from pyqtgraph.Qt import QtCore, QtGui
import numpy as np
import time
import msgpack
from .version import __version__

if(platform.system() == u'Windows'):
    import ctypes
    import pyreadline as readline
else:
    import readline

here = os.path.abspath(os.path.dirname(__file__))

version = __version__

MTU_SIZE = 1500
        

def getAuth(args, config):
    username = False
    password = False

    if(args.user):
        username = args.user
        if(not args.password):
            password = getpass.getpass("Password for " + username + ": ") 
        else:
            password = args.password
    
    else:
        if(config.has_section('auth')):
            if(config.has_option('auth','username')):
                username = config.get('auth','username')

            if(username):
                if(config.has_option('auth','password')):
                    password = config.get('auth','password')
                else:
                    password = getpass.getpass("Password for " + username + ": ") 
        else:
            # Config file has no value yet, might as well use the one passed in (or the default)
            config.add_section('auth')
            config.add_option('username', username)

    return { 'username' : username, 'password' : password }

class FEAMWaveform(object):
    sample_count = 0
    trigger_start = 0
    trigger_delay = 0
    waveform = array.array('B', [0] * (76*4*2*511))
    waveform_len = 0

    def __init__(self):
        pass

def getData(sub, q):
    msg = recv_msgpack(sub, flags=zmq.NOBLOCK)
    if(msg):
        q.put(msg)

class CaptureThread(QtCore.QThread):
    finished = QtCore.pyqtSignal(object)

    def __init__(self, sub, queue, parent=None):
        QtCore.QThread.__init__(self, parent)      
        self.queue = queue
        self.sub = sub

    def run(self):
        while True:
            getData(self.sub, self.queue)            

def recv_msgpack(socket, flags=0, protocol=-1):
    try:
        z = socket.recv(flags)
        return msgpack.unpackb(z, use_list=False)

    except Exception as e:
        if (str(e) == str("Resource temporarily unavailable")):
            # Socket not ready
            return None
        else:
            # Oopsy other error re-raise
            raise

q = queue.Queue()
plotter = []
feam_plot = [] 

# allocate a numpy array for the SCA plotter data
plot_data = []
for sca in range(4): 
    plot_data.append( [] )
    for ch in range(76):
        plot_data[sca].append( np.zeros( 511, np.dtype('i2') ) )

def update():
    global q, feam_plot, plotter
    
    while(not q.empty()):
        msg = q.get()
        # Lets do this! Fix up the waveform payload from the SCA into discrete waveforms
        for sample in range(511):
            sample_offset = sample * 76 * 4
            for ch in range(76): 
                ch_offset = ch * 4
                for sca in range(4):   
                    # SCA data arrangement
                    # [SCA0_ch0_s0][SCA1_ch0_s0][SCA2_ch0_s0][SCA3_ch0_s0]
                    # [SCA0_ch1_s0][SCA1_ch1_s0][SCA2_ch1_s0][SCA3_ch1_s0]
                    # ...
                    # [SCA0_ch75_s0][SCA1_ch75_s0][SCA2_ch75_s0][SCA3_ch75_s0]
                    # [SCA0_ch0_s1][SCA1_ch0_s1][SCA2_ch0_s1][SCA3_ch0_s1]
                    plot_data[sca][ch][sample] = msg[b'waveform'][ sample_offset + ch_offset + sca]
                    

        for sca in range(4):
            for ch in range(76):
                  feam_plot[sca][ch].setData( plot_data[sca][ch] )    

def main():
    try:
        prog='esper-wave'    

        parser = argparse.ArgumentParser(prog=prog)

        # Verbose, because sometimes you want feedback
        parser.add_argument('-v','--verbose', help="Verbose output", default=False, action='store_true')
        parser.add_argument('--version', action='version', version='%(prog)s ' + version)

        parser.add_argument("-f", "--config", default="test.ini", help="Config file for node")
        parser.add_argument("-s", "--storage", default="", help="Storage path for collected data")
        parser.add_argument("-u", "--user", default=False, help="User for Auth")
        parser.add_argument("-p", "--password", default=False, help="Password for Auth")
        parser.add_argument("ip", help="IP address of node to pull data from")
        #parser.add_argument("port", type=int, default=50005, help="Port of node to pull data from")

        # Put the arguments passed into args
        args = parser.parse_args()

        try: 
            # Load up config
            # Create config instance
            config = configparser.SafeConfigParser()

            # Load configuration file
            config.read(args.config)
        
            auth = getAuth(args, config)

            # if a username has been defined, then a password *MUST* have been grabbed, perform authentication
            if(auth['username']):
                print(auth['username'] + ' ' + auth['password'])

            addr = re.split(' :', args.ip)
            if(len(addr) < 2):
                addr.append( 50006 )

            # Setup 0MQ subscriber
            context = zmq.Context()
            sub = context.socket(zmq.SUB)
            sub.setsockopt_string(zmq.IDENTITY, "Hello")
            sub.setsockopt_string(zmq.SUBSCRIBE, "")
            sub.connect("tcp://" + str(addr[0]) + ':' + str(addr[1]))

            app = QtGui.QApplication([])

            w = QtGui.QWidget()
            layout = QtGui.QGridLayout()
            w.setLayout(layout)

            x = np.array([])
            for n in range(511):
                x = np.append( x, n )

            for sca in range(4):
                plotter.append( pg.PlotWidget() )
                plotter[sca].setXRange(0,510)
                plotter[sca].setYRange(-4096,4096)
                layout.addWidget( plotter[sca] )
                feam_plot.append( [] )
                for n in range(76):
                    feam_plot[sca].append( plotter[sca].plot(x, plot_data[sca][n], pen=(n, 76)) )  ## setting pen=None disables line drawing

                #plotter[sca].show()
            w.show()

            timer = QtCore.QTimer()
            timer.timeout.connect(update)
            timer.start(100)            
            
            thread = CaptureThread(sub,q)
            thread.start() 
            QtGui.QApplication.instance().exec_()
            thread.quit()            

            # No options selected, this should never be reached
            sys.exit(0) 

        except Exception as err:
            print(err)
            sys.exit(1)
              
    except KeyboardInterrupt:
        print("\nExiting " + prog)
        sys.exit(0)

if __name__ == "__main__":
    main()