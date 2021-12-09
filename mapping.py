import tty
import termios
import os
import sys
import math
from time import sleep, time
import json
import random

import paho
import paho.mqtt.client as mqtt
import paho.mqtt.subscribe as subscribe

orig_settings = termios.tcgetattr(sys.stdin)

print("ready")

position = [0., 0.]
crop = [0., 0., 1., 1.]
scale = 1.

def connect_mqtt():
    def on_connect(client, userdata, flags, rc):
        if rc == 0:
            print("Connected to MQTT Broker!")
        else:
            print("Failed to connect, return code %d\n", rc)
    client = paho.mqtt.client.Client(client_id="", clean_session=True, userdata=None, protocol=mqtt.MQTTv311, transport="tcp")
    client.on_connect = on_connect
    client.connect("master-1.local", port=1883)
    return client

SLAVE_ID = 30

def send_geometry(client):
    payload = json.dumps({"c":crop,"p":position,"s":scale})
    print(payload)
    client.publish(f"/m/{SLAVE_ID}/g", payload=payload, qos=0, retain=False)

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

client = connect_mqtt()
client.loop_start()

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
    send_geometry(client)

termios.tcsetattr(sys.stdin, termios.TCSADRAIN, orig_settings)
