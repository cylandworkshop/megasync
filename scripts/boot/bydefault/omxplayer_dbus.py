import os
import sys
import signal
import dbus
import getpass
from time import sleep, time
import subprocess

import threading

OMXPLAYER_DBUS_ADDR='/tmp/omxplayerdbus.%s' % getpass.getuser()

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
        self.stopped = None

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
        self.stopped = threading.Event()

        def loop(): # executed in another thread
            while not self.stopped.wait(0.02): # until stopped
                if self.Position() % 1 < 0.5:
                    os.system("echo 1 | sudo dd status=none of=/sys/class/leds/led0/brightness")
                else:
                    os.system("echo 0 | sudo dd status=none of=/sys/class/leds/led0/brightness")

        t = threading.Thread(target=loop)
        t.daemon = True # stop if the program exits
        t.start()

        try:
            self.methods.Play()
            return True
        except:
            print(e)
            return False

    def pause(self):
        if self.stopped is not None:
            self.stopped.set()
            self.stopped = None
        os.system("echo 0 | sudo dd status=none of=/sys/class/leds/led0/brightness")

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
            return None

    def setCrop(self, crop):
        self.methods.SetVideoCropPos(dbus.ObjectPath('/not/used'), dbus.String(" ".join([str(x) for x in crop])))

    def setVideoPos(self, pos):
        self.methods.VideoPos(dbus.ObjectPath('/not/used'), dbus.String(" ".join([str(x) for x in pos])))

    def getVideoResolution(self):
        try:
            return (self.properties.Get('org.mpris.MediaPlayer2.Player', 'ResWidth') / 1,
                    self.properties.Get('org.mpris.MediaPlayer2.Player', 'ResHeight') / 1)
        except Exception as e:
            return None