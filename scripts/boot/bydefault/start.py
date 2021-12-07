import os
import sys
import math
import signal
import getpass
from time import sleep, time
import subprocess
import json

import socket
from paho.mqtt import client as mqtt_client

from datetime import datetime
import ntplib

from screeninfo import get_monitors

from omxplayer_dbus import PlayerInterface
try:
    from subprocess import DEVNULL
except ImportError:
    import os
    DEVNULL = open(os.devnull, 'wb')

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

player = None
def run_omx(param):
    controller = PlayerInterface()
    process = subprocess.Popen(['omxplayer'] + param, preexec_fn=os.setsid, stdout=DEVNULL, stderr=DEVNULL, stdin=DEVNULL)
    if not controller.initialize():
        print("omx not ready")
        return None
    controller.pause()

    video_size = controller.getVideoResolution()

    print("run video", param, "video size:", video_size)

    return (controller, process, video_size)

def set_player_geometry(controller, video_size, screen_size, crop, position, scale):
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

# controller.setPosition(5)

my_id = socket.gethostname()[len("slave"):]
print("id:", my_id)

screen = get_monitors()[0]
screen_size = (screen.width, screen.height)
print("screen size:", screen_size)

time_diff = None

def sync_time(host):
    global time_diff

    try:
        ntp_client = ntplib.NTPClient()
        ntp_response = ntp_client.request(host, version=3)
    except:
        print("ntp server not available")
        return None

    time_diff = time() - ntp_response.tx_time

    print("time diff:", ntp_response.tx_time, time(), time_diff)
    return (())

def get_server_time():
    return time() - time_diff

def on_connect(client, userdata, flags, rc):
    print("connected to broker")

def on_message(client, userdata, msg):
    global player

    print("topic:", msg.topic)
    topic = msg.topic.split("/")[1:]

    if len(topic) < 3:
        print("topic not in layout")
        return

    if topic[0] != "m":
        print("non-slave topic")
        return

    if topic[1] != my_id:
        print("topic not for you")
        return

    method = topic[2]

    try:
        message = json.loads(msg.payload)
    except:
        print("non-json message")
        return

    print("message:", message)

    if method == "sync" and "host" in message:
        sync_time(message["host"])

    if method == "run" and type(message) == list:
        if player is not None:
            print("stop/remove prev video")
            os.killpg(os.getpgid(player[1].pid), signal.SIGTERM)
            sleep(2)
            player = None

        player = run_omx(message)

    if method == "g" and "c" in message and "p" in message and "s" in message:
        if player is None:
            print("no active player")
            return

        try:
            set_player_geometry(
                player[0], player[2], screen_size, message["c"], message["p"], message["s"]
            )
        except:
            print("set geometry failed")
            return

    # if method == "play" and player is not None:

        

'''
while True:
    message = str(server.recvfrom(256)[0])[2:-1]
    print("message:", message)
    if message[0] == "p":
        schedule_time = int(message[1:])
        print("scheduled to", schedule_time)
        break
'''

'''
while get_server_time() < schedule_time:
    sleep(0.01)

controller.play()
print("run video")

while True:
    sleep(1)
    print(controller.Position() - (get_server_time() - schedule_time))
'''

broker = 'master1.local'
port = 1883
topic = f"/m/{my_id}/#"
# topic = "#"
client_id = socket.gethostname() + "-" + str(time())[-4:]

print("connecting as", client_id)

client = mqtt_client.Client(client_id)
client.connect(broker, port)
client.subscribe(topic)
client.on_message = on_message
client.on_connect = on_connect
client.loop_forever()