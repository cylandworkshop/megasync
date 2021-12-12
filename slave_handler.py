import curses
import json
from time import time

class SlaveHandler():
    def __init__(self, client, idx, logger):
        self.logger = logger
        self.client = client
        self.idx = idx

        self.time_sync_status = "no sync"
        self.last_status = None
        self.last_status_time = time()

        self.position = [0., 0.]
        self.crop = [0., 0., 1., 1.]
        self.scale = 1.

        self.logger(f"add {self.idx} handler")

    def update(self, stdscr, x, y):
        color = curses.color_pair(3)


        if self.last_status is None:
            color = curses.color_pair(5)
        elif self.last_status[0] != 0:
            color = curses.color_pair(4)
        
        if time() - self.last_status_time > 0.7:
            color = curses.color_pair(6)

        status = "???"
        if self.last_status is not None:
            if self.last_status[0] == 0:
                status = "idle"
            elif self.last_status[0] == 1:
                status = "stop"
            elif self.last_status[0] == 2:
                status = "wait"
            elif self.last_status[0] == 3:
                status = "play"

        stdscr.addstr(y, x, f"slave {self.idx}", color)
        stdscr.addstr(" %s (%.01f) |" % (status, time() - self.last_status_time))
        stdscr.addstr(f" {self.time_sync_status}")
        if self.last_status is not None and self.last_status[1] is not None:
            stdscr.addstr(y + 1, x, "pos %02d:%06.3f | sheduled 0:00.000" "" % (
                int(self.last_status[1]/60),
                self.last_status[1] % 60
            ))

    def send_message(self, topic, payload, qos=1):
        self.client.publish(f"/m/{self.idx}/{topic}", payload=json.dumps(payload), qos=qos, retain=False)


    def send_geometry(self, qos=0):
        self.send_message("g", {"c":self.crop,"p":self.position,"s":self.scale}, qos=qos)


    def sync_time(self, host):
        self.time_sync_status = "sync in progress"
        self.send_message("sync", host)

    def run(self, param):
        self.send_message("run", param)
        self.last_status = None

    def play(self):
        self.send_message("play", None)
        self.last_status = None

    def pause(self):
        self.send_message("pause", None)
        self.last_status = None

    def schedule(self, time):
        self.send_message("s", time)
        self.last_status = None

    def seek(self, position):
        self.send_message("seek", position)
        self.last_status = None

    def kill(self):
        self.send_message("kill", None)
        self.last_status = None

    def handle_message(self, topic, payload):
        if topic[0] != "s":
            return
        if int(topic[1]) != self.idx:
            return

        if topic[2] != "s":
            self.logger(f"{self.idx}: {topic[2]} {str(payload)}")
        else:
            self.last_status = payload
            self.last_status_time = time()

        if topic[2] == "sync":
            self.logger(f"sync result: {str(payload)}")
            self.time_sync_status = "sync: " + str(payload)
    
    def set_corner(self, corner, x):
        if x == "a":
            # print("left")
            self.crop[corner * 2 + 0] -= 0.002
        elif x == "d":
            # print("right")
            self.crop[corner * 2 + 0] += 0.002
        elif x == "w":
            # print("up")
            self.crop[corner * 2 + 1] -= 0.002
        elif x == "s":
            # print("down")
            self.crop[corner * 2 + 1] += 0.002

    def set_position(self, x):
        if x == "a":
            # print("left")
            self.position[0] -= 0.002
        elif x == "d":
            # print("right")
            self.position[0] += 0.002
        elif x == "w":
            # print("up")
            self.position[1] -= 0.002
        elif x == "s":
            # print("down")
            self.position[1] += 0.002

    def set_scale(self, x):
        if x == "z":
            self.scale += 0.01
        elif x == "x":
            self.scale -= 0.01
