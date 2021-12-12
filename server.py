import curses
from time import sleep, time

import paho
import paho.mqtt.client as mqtt
import paho.mqtt.subscribe as subscribe

import json

from slave_handler import SlaveHandler

#slaves = ["slave" + str(x) for x in range(0,10)]
slave_ids = [x for x in range(1, 40)]
# slave_ids = [0, 1, 2, 3, 50]

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
    client.connect("master-50.local", port=1883)
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

corner = 0
move = False

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

        # append_log(str(msg.payload))
        payload = json.loads(msg.payload)
        # append_log(str(payload))

        for slave in slaves:
            slave.handle_message(topic, payload)

    client.on_message = on_message

    select_slave = None
    mapping = False

    def handle_mapping(x, idx):
        global corner
        global move

        if x == "f":
            if corner == 0:
                corner = 1
                append_log("set corner 1")
            elif corner == 1:
                corner = 0
                append_log("set corner 0")
        elif x == "v":
            move = not move
            append_log(f"set move {move}")
        
        elif x == "z" or x == "x":
            slaves[idx].set_scale(x)
        else:
            if move:
                slaves[idx].set_position(x)
            else:
                slaves[idx].set_corner(corner, x)
        
        slaves[idx].send_geometry()
    
    start_time = time()
    while True:
        size = stdscr.getmaxyx()
        song_duration = time() - start_time

        # draw song duration
        stdscr.addstr(size[0] - 1, 0, " " * int(size[1]/2))
        stdscr.addstr(size[0] - 1, 0, "%02d:%02d:%06.3f" % (
            int(song_duration/3600),
            int(song_duration/60) % 60,
            song_duration % 60
        ), curses.color_pair(1))
        stdscr.addstr(f" {BPM} BPM {MEASURE[0]}/{MEASURE[1]} (x,y): {size} select: {str(select_slave)} map: {mapping} c: {corner} m: {move}")

        measure = (song_duration/BEAT) % MEASURE[0]
        
        draw_beat(stdscr, measure)
        render_log_window(stdscr, log)

        for i, slave in enumerate(slaves):
            draw_slave(stdscr, slave, i)

        def apply_slave(selector, method):
            if selector is None:
                for slave in slaves:
                    method(slave)
            else:
                method(slaves[selector])

        char = stdscr.getch()
        if char > 0:
            if char == ord('m'):
                if mapping:
                    append_log("disable mapping")
                    mapping = False
                else:
                    append_log("enable mapping")
                    mapping = True
            elif mapping and select_slave is not None:
                handle_mapping(chr(char), select_slave)

            elif char == ord(' '):
                current_bar = int(song_duration / BAR)
                start_time = time() - current_bar * BAR
            elif char == curses.KEY_LEFT:
                start_time += 1/BEAT
            elif char == curses.KEY_RIGHT:
                start_time -= 1/BEAT

            elif char == ord('t'):
                append_log("start sync time")
                apply_slave(select_slave, lambda x: x.sync_time("aanper-thinkpad.local"))

            elif char == ord('r'):
                append_log("run omx")
                apply_slave(select_slave, lambda x: x.run(["/data/A1.mp4"]))

            elif char == ord('o'):
                append_log("play")
                # apply_slave(select_slave, lambda x: x.play())
                # TODO get time from centeral NTP
                apply_slave(select_slave, lambda x: x.schedule(time() + 2))

            elif char == ord('h'):
                append_log("seek")
                apply_slave(select_slave, lambda x: x.seek(5))

            elif char == ord('p'):
                append_log("pause")
                apply_slave(select_slave, lambda x: x.pause())

            elif char == ord('k'):
                append_log("kill")
                apply_slave(select_slave, lambda x: x.kill())

            elif char == ord('/'):
                if select_slave is None:
                    append_log("start select slave")
                    select_slave = 0
                else:
                    append_log("stop select slave")
                    select_slave = None

            elif char == curses.KEY_UP:
                if select_slave is not None and select_slave < len(slaves) - 1:
                    select_slave += 1
            elif char == curses.KEY_DOWN:
                if select_slave is not None and select_slave > 0:
                    select_slave -= 1

            else:
                append_log(f"you pressed {str(char)}")
        
        sleep(0.05)
    return 0

# stdscr.refresh()

def main():
    return curses.wrapper(c_main)


if __name__ == '__main__':
    exit(main())