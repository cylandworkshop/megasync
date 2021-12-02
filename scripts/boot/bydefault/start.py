import os
import sys
import math
import signal
import dbus
import getpass
from time import sleep, time
import subprocess

import socket

from datetime import datetime
import ntplib


try:
    from subprocess import DEVNULL
except ImportError:
    import os
    DEVNULL = open(os.devnull, 'wb')

OMXPLAYER = 'omxplayer'
OMXPLAYER_DBUS_ADDR='/tmp/omxplayerdbus.%s' % getpass.getuser()


#
# D-Bus player interface
#
class PlayerInterface():
    def _get_dbus_interface(self):
        try:
            bus = dbus.bus.BusConnection(
                open(OMXPLAYER_DBUS_ADDR).readlines()[0].rstrip())
            proxy = bus.get_object(
                'org.mpris.MediaPlayer2.omxplayer',
                '/org/mpris/MediaPlayer2',
                introspect=False)
            self.methods = dbus.Interface(
                proxy, 'org.mpris.MediaPlayer2.Player')
            self.properties = dbus.Interface(
                proxy, 'org.freedesktop.DBus.Properties')
            return True
        except Exception as e:
            print("WARNING: dbus connection could not be established")
            print(e)
            sleep(5)
            return False

    def initialize(self):
        sleep(3) # wait for omxplayer to appear on dbus
        return self._get_dbus_interface()

    def playPause(self):
        try:
            self.methods.Action(16)
            return True
        except:
            print(e)
            return False

    def play(self):
        try:
            self.methods.Play()
            return True
        except:
            print(e)
            return False

    def pause(self):
        try:
            self.methods.Pause()
            return True
        except:
            print(e)
            return False


    def setPosition(self, seconds):
        try:
            self.methods.SetPosition(
                dbus.ObjectPath('/not/used'),
                dbus.Int64(seconds * 1000000))
        except Exception as e:
            print(e)
            return False

        return True

    def Position(self):
        try:
            return self.properties.Get(
                'org.mpris.MediaPlayer2.Player',
                'Position') / 1e6
        except Exception as e:
            return False

def setInterval(interval):
    def decorator(function):
        def wrapper(*args, **kwargs):
            stopped = threading.Event()

            def loop(): # executed in another thread
                while not stopped.wait(interval): # until stopped
                    function(*args, **kwargs)

            t = threading.Thread(target=loop)
            t.daemon = True # stop if the program exits
            t.start()
            return stopped
        return wrapper
    return decorator

print("yo")

localIP     = "0.0.0.0"
localPort   = 20001

NTP_SERVER = "192.168.1.2"

server = socket.socket(family=socket.AF_INET, type=socket.SOCK_DGRAM)
server.bind((localIP, localPort))
print("UDP server up and listening")

controller = PlayerInterface()
process = subprocess.Popen([OMXPLAYER, "/data/worktown.mp4"], preexec_fn=os.setsid, stdout=DEVNULL, stderr=DEVNULL, stdin=DEVNULL)
if not controller.initialize():
    print("omx not ready")
    exit(0)


controller.pause()
controller.setPosition(5)

ntp_client = ntplib.NTPClient()
ntp_response = ntp_client.request(NTP_SERVER, version=3)
time_diff = time() - ntp_response.tx_time

print("time diff:", ntp_response.tx_time, time(), time_diff)

while True:
    message = str(server.recvfrom(256)[0])[2:-1]
    print("message:", message)
    if message[0] == "p":
        schedule_time = int(message[1:])
        print("scheduled to", schedule_time)
        break

def get_server_time():
    return time() - time_diff

while get_server_time() < schedule_time:
    sleep(0.01)

controller.play()
print("run video")

while True:
    sleep(1)
    print(controller.Position() - (get_server_time() - schedule_time))