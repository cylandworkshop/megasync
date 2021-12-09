import curses
import json
from time import time

class SlaveHandler():
    def __init__(self, client, idx, logger):
        self.logger = logger
        self.client = client
        self.idx = idx

        self.time_sync_status = "no sync"
        self.last_status = [0, None]
        self.last_status_time = time()

        self.logger(f"add {self.idx} handler")

    def update(self, stdscr, x, y):
        status = "???"
        if self.last_status[0] == 0:
            status = "idle"
        elif self.last_status[0] == 1:
            status = "stop"
        elif self.last_status[0] == 2:
            status = "wait"
        elif self.last_status[0] == 3:
            status = "play"

        stdscr.addstr(y, x, f"slave {self.idx}", curses.color_pair(3))
        stdscr.addstr(" %s (%.01f) |" % (status, time() - self.last_status_time))
        stdscr.addstr(f" {self.time_sync_status}")
        if self.last_status[1] is not None:
            stdscr.addstr(y + 1, x, "pos %02d:%06.3f | sheduled 0:00.000" "" % (
                int(self.last_status[1]/60),
                self.last_status[1] % 60
            ))

    def send_message(self, topic, payload, qos=1):
        self.client.publish(f"/m/{self.idx}/{topic}", payload=json.dumps(payload), qos=qos, retain=False)

    def sync_time(self, host):
        self.time_sync_status = "sync in progress"
        self.send_message("sync", host)

    def run(self, param):
        self.send_message("run", param)

    def play(self):
        self.send_message("play", None)

    def pause(self):
        self.send_message("pause", None)

    def kill(self):
        self.send_message("kill", None)

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
