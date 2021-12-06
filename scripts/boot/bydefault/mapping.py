import tty
import termios
import os
import sys
import math
import signal
import dbus
import getpass
from time import sleep, time
import subprocess
from screeninfo import get_monitors

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


controller = PlayerInterface()
process = subprocess.Popen([OMXPLAYER, "/data/videoframe.mp4"], preexec_fn=os.setsid, stdout=DEVNULL, stderr=DEVNULL, stdin=DEVNULL)
if not controller.initialize():
    print("omx not ready")
    exit(0)

controller.pause()

orig_settings = termios.tcgetattr(sys.stdin)

print("ready")
video_size = controller.getVideoResolution()
screen = get_monitors()[0]
screen_size = (screen.width, screen.height)

print("video size:", video_size, "screen size:", screen_size)

position = [0., 0.]
crop = [0., 0., 1., 1.]
scale = 1.

last_crop = (0,0,0,0)
last_win = (0,0,0,0)

def set_window():
    global last_crop
    global last_win

    last_crop = (
        crop[0] * video_size[0],
        crop[1] * video_size[1],
        crop[2] * video_size[0],
        crop[3] * video_size[1]
    )
    last_win = (
        (position[0] +  crop[0]) * screen_size[0],
        (position[1] + crop[1]) * screen_size[1],
        (position[0] + scale * crop[2]) * screen_size[0],
        (position[1] + scale * crop[3]) * screen_size[1]
    )

    controller.setCrop(last_crop)
    controller.setVideoPos(last_win)

def set_corner(corner, x):
    global crop
    
    if x == "a":
        print("left")
        crop[corner * 2 + 0] -= 0.002
    elif x == "d":
        print("right")
        crop[corner * 2 + 0] += 0.002
    elif x == "w":
        print("up")
        crop[corner * 2 + 1] -= 0.002
    elif x == "s":
        print("down")
        crop[corner * 2 + 1] += 0.002

def set_position(x):
    global position
    
    if x == "a":
        print("left")
        position[0] -= 0.002
    elif x == "d":
        print("right")
        position[0] += 0.002
    elif x == "w":
        print("up")
        position[1] -= 0.002
    elif x == "s":
        print("down")
        position[1] += 0.002

corner = 0
move = False

tty.setcbreak(sys.stdin)
x = 0
while x != chr(27): # ESC
    x = sys.stdin.read(1)[0]
    if x == "f":
        if corner == 0:
            corner = 1
            print("set corner 1")
        elif corner == 1:
            corner = 0
            print("set corner 0")
    if x == "m":
        move = not move
        print("set move", move)
    
    elif x == "z":
        scale += 0.01
    elif x == "x":
        scale -= 0.01
    elif x == "\n":
        print("saved: --win %d,%d,%d,%d --crop %d,%d,%d,%d" % (
            last_win[0], last_win[1], last_win[2], last_win[3],
            last_crop[0], last_crop[1], last_crop[2], last_crop[3]
            )
        )
    else:
        if move:
            set_position(x)
        else:
            set_corner(corner, x)
    set_window()

os.killpg(os.getpgid(process.pid), signal.SIGTERM)
termios.tcsetattr(sys.stdin, termios.TCSADRAIN, orig_settings)
