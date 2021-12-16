import os
import sys
import math
import signal
import getpass
from time import sleep, time
import subprocess
import threading
import json
import statistics

import socket
from paho.mqtt import client as mqtt_client

from datetime import datetime
import ntplib

from screeninfo import get_monitors

import random

from omxplayer_dbus import PlayerInterface
try:
    from subprocess import DEVNULL
except ImportError:
    import os
    DEVNULL = open(os.devnull, 'wb')

from json import encoder
encoder.FLOAT_REPR = lambda o: format(o, '.3f')

my_id = socket.gethostname().split("-")[1].split(".")[0]
print("id:", my_id)

broker = 'master-50.local'
port = 1883
# topic = "#"
client_id = my_id + "-" + str(time())[-4:]
topic = f"/m/{my_id}/#"

random.seed()
time_diff = None
time_stdev = None

def sync_time_iter(ntp_client, host, accuracy, write_time):
    global time_diff
    global time_stdev

    print(f"syncing time, host: {host}, write: {write_time}")

    _time_diffs = []
    offsets = []

    for _ in range(3):
        try:
            ntp_response = ntp_client.request(host, version=3)
            print(f"tx: {ntp_response.tx_time} delay:{ntp_response.delay/2}")
        except Exception as e:
            print("ntp server not available", e)
            if write_time:
                return False
            else:
                return True

        _time_diffs.append(time() - (ntp_response.tx_time + ntp_response.delay/2))
        offsets.append(ntp_response.delay/2)

        sleep(1)

    diff_median = statistics.median(_time_diffs)
    diff_stdev = statistics.stdev(_time_diffs)
    offset_median = statistics.median(offsets)

    print(f"median: {diff_median}, stdev: {diff_stdev}, latency: {offset_median}")

    if diff_stdev > accuracy:
        print("low accuracy")
        if write_time:
            time_diff = None
            return False
        else:
            return True # just wait for next resync

    if write_time:
        time_diff = diff_median
        time_stdev = diff_stdev
        return True
    else:
        time_drift = abs(time_diff - diff_median)
        print(f"drift {time_drift}")

        if time_drift > accuracy:
            print(f"time mismatch")
            time_diff = None
            return False
        else:
            return True
    
    # something wrong
    return False

NTP_HOST = broker
NTP_ACCURACY = 0.01

sync_time_resync = None
def sync_time():
    global sync_time_resync

    if sync_time_resync is not None:
        sync_time_resync.set()

    ntp_client = ntplib.NTPClient()

    sync_time_resync = threading.Event()

    def sync_time_routine():
        sleep(random.randint(100, 1000) / 1000.) # wait first try
        while True:
            #syncing until true
            while not sync_time_iter(ntp_client, NTP_HOST, NTP_ACCURACY, True):
                sleep(random.randint(500, 2000) / 1000.) # retry delay

            sync_time_resync.wait()

    sync_time_thread = threading.Thread(target=sync_time_routine)
    sync_time_thread.daemon = True # stop if the program exits
    sync_time_thread.start()

    return None

def get_server_time():
    if time_diff is None:
        return None

    return time() - time_diff

NO_PLAYER = 0
STOP = 1
SHEDULED = 2
PLAY = 3
status = NO_PLAYER

handle_schedule_time = None

def schedule_play(controller, schedule_time):
    global handle_schedule_time

    stopped = threading.Event()

    if get_server_time() is None:
        print("no server time")
        return None

    print("shedule to", schedule_time)
    handle_schedule_time = schedule_time

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

def set_player_geometry(controller, video_size, screen_size, crop, position):
    last_crop = (
        crop[0] * video_size[0],
        crop[1] * video_size[1],
        crop[2] * video_size[0],
        crop[3] * video_size[1]
    )
    last_win = (
        (position[0] +  crop[0]) * screen_size[0],
        (position[1] + crop[1]) * screen_size[1],
        (position[0] + position[2] * crop[2]) * screen_size[0],
        (position[1] + position[3] * crop[3]) * screen_size[1]
    )

    controller.setCrop(last_crop)
    controller.setVideoPos(last_win)

# controller.setPosition(5)

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
    server_time = get_server_time()
    if status == PLAY and player is not None and handle_schedule_time is not None and server_time is not None:
        position = player[0].Position() - (server_time - handle_schedule_time)
    elif status == STOP and player is not None:
        if player is not None:
            position = player[0].Position()
        else:
            position = 0
    elif status == SHEDULED:
        position = handle_schedule_time
    else:
        position = None

    time_status = None
    if time_diff is not None:
        time_status = time_stdev

    send_message("s", [status, position, time_status], qos=qos)

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

start_send_status_handler = None
def on_connect(_client, _userdata, _flags, _rc):
    global start_send_status_handler
    global time_diff
    global time_stdev

    time_diff = None
    time_stdev = None
    print("connected to broker")
    _client.subscribe(topic)
    if start_send_status_handler is None:
        start_send_status_handler = start_send_status()
    sync_time()

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

    if method == "run" and type(message) == list:
        if player is not None:
            print("stop/remove prev video")
            player[0].pause()
            sleep(0.1)
            os.killpg(os.getpgid(player[1].pid), signal.SIGTERM)
            player = None
            sleep(2)

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
                player[0], player[2], screen_size, message["c"], message["p"]
            )
            return None
        except:
            return (("err", "set geometry failed"))

    elif method == "play":
        if player is None:
            return (("err", "no active player"))

        print("play")
        player[0].play()
        handle_schedule_time = get_server_time()
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

        if scheduler is not None:
            print("cancel prev schedule")
            scheduler.set()
            scheduler = None

        print("stop/remove prev video")
        player[0].pause()
        sleep(0.1)
        os.killpg(os.getpgid(player[1].pid), signal.SIGTERM)
        player = None
        status = NO_PLAYER
        sleep(2)
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

print("connecting as", client_id)

client = mqtt_client.Client(client_id)
while True:
    try:
        client.connect(broker, port, keepalive=4)
        break
    except Exception as e:
        print(e)

client.on_message = on_message
client.on_connect = on_connect
client.reconnect_delay_set(min_delay=1, max_delay=2)
client.loop_forever(retry_first_connection=True)