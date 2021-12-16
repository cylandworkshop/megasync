import curses
import json
from time import time

class SlaveHandler():
    def __init__(self, client, idx, logger):
        self.logger = logger
        self.client = client
        self.idx = idx

        self.time_sync = False
        self.last_status = None
        self.last_status_time = time()

        self.position = [0., 0., 1., 1.]
        self.crop = [0., 0., 1., 1.]
        self.scale = 1.

        self.logger(f"add {self.idx} handler")

    def get_idx(self):
        return self.idx

    def update(self, stdscr, x, y, server_time):
        color = curses.color_pair(3)


        if self.last_status is None:
            color = curses.color_pair(5)
        elif self.last_status[0] != 0:
            color = curses.color_pair(4)
        
        if time() - self.last_status_time > 0.7:
            color = curses.color_pair(6)

        status = "???"
        position_text = ""
        if self.last_status is not None:
            if self.last_status[0] == 0:
                status = "idle"
            elif self.last_status[0] == 1 and self.last_status[1] is not None:
                status = "stop"
                position_text = "stop at: %02d:%06.3f" % (
                    int(self.last_status[1]/60),
                    self.last_status[1] % 60
                )
            elif self.last_status[0] == 2:
                status = "wait"
                position_text = "%.03f" % ((self.last_status[1] - server_time))
            elif self.last_status[0] == 3:
                status = "play"
                position_text = "drift: %.03f" % ((self.last_status[1]))

        time_status = ""
        time_color = curses.color_pair(0)
        if self.last_status is not None and self.last_status[2] is not None:
            time_status = "sync: " + "%.03f" % ((self.last_status[2]))
        else:
            if self.time_sync:
                time_status = "no sync"
                time_color = curses.color_pair(2)
            else:
                time_status = "wait sync"
                time_color = curses.color_pair(7)

        stdscr.addstr(y, x, f"slave {self.idx}", color)
        stdscr.addstr(" %s (%.01f) |" % (status, time() - self.last_status_time))
        stdscr.addstr(f" {time_status}", time_color)
        stdscr.addstr(y + 1, x, position_text)

    def send_message(self, topic, payload, qos=1):
        self.client.publish(f"/m/{self.idx}/{topic}", payload=json.dumps(payload), qos=qos, retain=False)


    def send_geometry(self, qos=0):
        # self.logger(f"c:{self.crop} p:{self.position}")
        self.send_message("g", {"c":self.crop,"p":self.position}, qos=qos)


    def sync_time(self, host):
        self.time_sync = True
        self.send_message("sync", {"host": host, "acc": 0.05})

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
        # self.send_geometry(qos=1)
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

    def set_position(self, corner, x):
        if x == "a":
            # print("left")
            self.position[corner * 2 + 0] -= 0.002
        elif x == "d":
            # print("right")
            self.position[corner * 2 + 0] += 0.002
        elif x == "w":
            # print("up")
            self.position[corner * 2 + 1] -= 0.002
        elif x == "s":
            # print("down")
            self.position[corner * 2 + 1] += 0.002

    def get_mapping(self):
        return {"position": self.position, "crop": self.crop}

    def set_mapping(self, mapping):
        self.position = mapping["position"]
        self.crop = mapping["crop"]
