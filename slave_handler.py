import curses
import json

class SlaveHandler():
    def __init__(self, client, idx, logger):
        self.logger = logger
        self.client = client
        self.idx = idx

        self.time_sync_status = "no sync"

        self.logger(f"add {self.idx} handler")

    def update(self, stdscr, x, y):
        stdscr.addstr(y, x, f"slave {self.idx}", curses.color_pair(3))
        stdscr.addstr(f" no video | {self.time_sync_status}")
        stdscr.addstr(y + 1, x, "sheduled 0:32.234 | position 0:04.234")

    def send_message(self, topic, payload, qos=1):
        self.client.publish(f"/m/{self.idx}/{topic}", payload=json.dumps(payload), qos=qos, retain=False)

    def sync_time(self, host):
        self.time_sync_status = "sync in progress"
        self.send_message("sync", host)

    def handle_message(self, topic, payload):
        if topic[0] != "s":
            return
        if int(topic[1]) != self.idx:
            return

        if topic[2] != "s":
            self.logger(f"{self.idx}: {topic[2]} {str(payload)}")

        if topic[2] == "sync":
            self.logger(f"sync result: {str(payload)}")
            self.time_sync_status = "sync: " + str(payload)
