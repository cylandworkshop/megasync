import os
import sys
import math
import signal
import getpass
from time import sleep, time
import subprocess
import threading
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

from json import encoder
encoder.FLOAT_REPR = lambda o: format(o, '.3f')

time_diff = None

def sync_time(host):
    global time_diff

    try:
        ntp_client = ntplib.NTPClient()
        ntp_response = ntp_client.request(host, version=3)
    except:
        print("ntp server not available")
        return False

    time_diff = time() - ntp_response.tx_time

    print("time diff:", ntp_response.tx_time, time(), time_diff)
    return True

def get_server_time():
    if time_diff is None:
        return None

    return time() - time_diff

NO_PLAYER = 0
STOP = 1
SHEDULED = 2
PLAY = 3
status = NO_PLAYER

def schedule_play(controller, schedule_time):
    stopped = threading.Event()

    if get_server_time() is None:
        print("no server time")
        return None

    print("shedule to", schedule_time)

    def waiter():
        global status
        while True:
            d = schedule_time - get_server_time()
            # print("wait", d)
            if d < 0:
                print("sheduled play")
                controller.play()
                status = PLAY
                break
            if stopped.wait(0.005):
                print("shedule canceled")
                status = STOP
                break

    t = threading.Thread(target=waiter)
    t.daemon = True # stop if the program exits
    t.start()
    return stopped

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

client = None

def send_message(topic, message, qos=0):
    if client is None:
        print("no client")
        return
    payload = json.dumps(message)
    full_topic = f"/s/{my_id}/{topic}"
    # print(f"send {full_topic}: {payload}")

    client.publish(full_topic, payload=payload, qos=qos, retain=False)

def send_status(qos=0):
    position = None
    if (status == STOP or status == PLAY) and player is not None:
        position = player[0].Position()
    elif status == SHEDULED:
        position = 0 # TODO get scheduled diff
    else:
        position = None

    send_message("s", json.dumps([status, position]), qos=qos)

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

@setInterval(.5)
def start_send_status():
    send_status()

def on_connect(_client, _userdata, _flags, _rc):
    print("connected to broker")
    start_send_status()

scheduler = None
def handle_message(msg):
    global player
    global scheduler
    global status

    print("topic:", msg.topic)
    topic = msg.topic.split("/")[1:]

    if len(topic) < 3:
        return (("err", "topic not in layout"))

    if topic[0] != "m":
        return (("err", "non-slave topic"))

    if topic[1] != my_id:
        return (("err", "topic not for you"))

    method = topic[2]

    try:
        message = json.loads(msg.payload)
    except:
        return (("err", "non-json message"))

    print("message:", message)

    if method == "sync" and type(message) == str:
        return (("sync", sync_time(message)))

    elif method == "run" and type(message) == list:
        if player is not None:
            print("stop/remove prev video")
            os.killpg(os.getpgid(player[1].pid), signal.SIGTERM)
            sleep(2)
            player = None

        player = run_omx(message)

        if player is None:
            return (("err", "cannot start omx/controller"))

        status = STOP

        return None

    elif method == "g" and "c" in message and "p" in message and "s" in message:
        if player is None:
            return (("err", "no active player"))

        try:
            set_player_geometry(
                player[0], player[2], screen_size, message["c"], message["p"], message["s"]
            )
            return None
        except:
            return (("err", "set geometry failed"))

    elif method == "play":
        if player is None:
            return (("err", "no active player"))

        print("play")
        player[0].play()
        status = PLAY
        return None

    elif method == "pause":
        if player is None:
            return (("err", "no active player"))

        print("pause")
        player[0].pause()
        status = STOP
        return None

    elif method == "seek" and (type(message) == int or type(message) == float):
        if player is None:
            return (("err", "no active player"))

        print("seek to", message)
        player[0].setPosition(message)
        return None

    elif method == "kill":
        if player is None:
            return (("err", "no active player"))

        print("stop/remove prev video")
        os.killpg(os.getpgid(player[1].pid), signal.SIGTERM)
        sleep(2)
        player = None
        status = NO_PLAYER
        return None

    elif method == "s" and (type(message) == int or type(message) == float):
        if player is None:
            return (("err", "no active player"))

        player[0].pause()

        if scheduler is not None:
            print("cancel prev schedule")
            scheduler.set()
            scheduler = None

        print("schedule to", message)
        scheduler = schedule_play(player[0], message)
        if scheduler is not None:
            status = SHEDULED
            return None
        else:
            return (("err", "cannot schedule (maybe not in sync)"))

    elif method == "cancel":
        if player is None:
            return (("err", "no active player"))

        player[0].pause()

        print("cancel schedule")
        if scheduler is not None:
            scheduler.set()
            scheduler = None
            status = STOP
        return None
    else:
        return (("err", "unrecognized method or format"))

def on_message(_client, _userdata, msg):
    res = handle_message(msg)
    if res is not None:
        print(res)
        send_message(res[0], res[1], qos=1)
    else:
        send_status(qos=1)

'''
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