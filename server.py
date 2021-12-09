import curses
from time import sleep, time

import paho
import paho.mqtt.client as mqtt
import paho.mqtt.subscribe as subscribe

import json

from slave_handler import SlaveHandler

#slaves = ["slave" + str(x) for x in range(0,10)]
slave_ids = [1, 30]

LOG_WINDOW_HEIGHT = 10

def render_log_window(stdscr, log):
    size = stdscr.getmaxyx()

    for i, log_line in enumerate(log[-min(LOG_WINDOW_HEIGHT, size[0]):]):
        log_line = log_line[:size[1]]
        padding_len = len(log_line)
        stdscr.addstr(size[0] - LOG_WINDOW_HEIGHT + i, int(size[1]/2), log_line + " " * padding_len)

log = []
def append_log(log_str):
    global log
    log.append(str(log_str))
    log = log[-LOG_WINDOW_HEIGHT:]

def connect_mqtt():
    def on_connect(client, userdata, flags, rc):
        if rc == 0:
            append_log("Connected to MQTT Broker!")
        else:
            append_log("Failed to connect, return code %d\n" % rc)

    client = paho.mqtt.client.Client(client_id="", clean_session=True, userdata=None, protocol=mqtt.MQTTv311, transport="tcp")
    client.on_connect = on_connect
    client.connect("master-1.local", port=1883)
    client.subscribe("/s/#")
    return client

BPM = 120
MEASURE = (4,4)
BEAT = 60/(BPM * (MEASURE[1]/4))
BAR = BEAT * MEASURE[0]

def draw_beat(stdscr, measure):
    size = stdscr.getmaxyx()

    color = curses.color_pair(2) if int(measure) == 0 else curses.color_pair(1)
    for y in range(2, 5):
        for x in range (0, 5):
            stdscr.move(size[0] - y, x)
            if measure % 1 < 0.15:
                stdscr.addch(curses.ACS_BOARD, color)
            else:
                stdscr.addch(" ")
    stdscr.addstr(size[0] - 3, 1, f"{int(measure) + 1}/{MEASURE[1]}")
    stdscr.move(0, 0)

SLAVE_LINES = 2

def draw_slave(stdscr, slave, idx):
    size = stdscr.getmaxyx()
    unwrap_y = idx * SLAVE_LINES
    size_y = size[0] - LOG_WINDOW_HEIGHT - 1
    y = int(unwrap_y % size_y)
    x = int(unwrap_y / size_y) * int(size[1]/4)

    for i in range(SLAVE_LINES):
        stdscr.addstr(y + i, x, " " * int(size[1]/4))

    slave.update(stdscr, x, y)


def c_main(stdscr):
    stdscr.nodelay(True)
    curses.init_pair(1, curses.COLOR_YELLOW, curses.COLOR_BLACK)
    curses.init_pair(2, curses.COLOR_RED, curses.COLOR_BLACK)
    curses.init_pair(3, curses.COLOR_WHITE, curses.COLOR_BLUE)
    curses.init_pair(4, curses.COLOR_WHITE, curses.COLOR_GREEN)
    curses.init_pair(5, curses.COLOR_WHITE, curses.COLOR_YELLOW)
    curses.init_pair(6, curses.COLOR_WHITE, curses.COLOR_RED)

    client = connect_mqtt()
    client.loop_start()

    slaves = [SlaveHandler(client, x, append_log) for x in slave_ids]

    def on_message(_client, _userdata, msg):
        topic = msg.topic.split("/")[1:]
        payload = json.loads(msg.payload)

        for slave in slaves:
            slave.handle_message(topic, payload)

    client.on_message = on_message
    
    start_time = time()
    while True:
        size = stdscr.getmaxyx()
        song_duration = time() - start_time

        # draw song duration
        stdscr.addstr(size[0] - 1, 0, "%02d:%02d:%06.3f" % (
            int(song_duration/3600),
            int(song_duration/60) % 60,
            song_duration % 60
        ), curses.color_pair(1))
        stdscr.addstr(f" {BPM} BPM {MEASURE[0]}/{MEASURE[1]} (x,y): {size}")

        measure = (song_duration/BEAT) % MEASURE[0]
        
        draw_beat(stdscr, measure)
        render_log_window(stdscr, log)

        for i, slave in enumerate(slaves):
            draw_slave(stdscr, slave, i)

        char = stdscr.getch()
        if char > 0:
            append_log(f"you pressed {str(char)}")

            if char == ord(' '):
                current_bar = int(song_duration / BAR)
                start_time = time() - current_bar * BAR
            elif char == curses.KEY_LEFT:
                start_time += 1/BEAT
            elif char == curses.KEY_RIGHT:
                start_time -= 1/BEAT

            elif char == ord('t'):
                for slave in slaves:
                    slave.sync_time("master1.local")
        
    return 0

# stdscr.refresh()

def main():
    return curses.wrapper(c_main)


if __name__ == '__main__':
    exit(main())