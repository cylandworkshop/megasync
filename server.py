import curses
from time import sleep, time
import threading

import paho
import paho.mqtt.client as mqtt
import paho.mqtt.subscribe as subscribe

import ntplib

import json

from slave_handler import SlaveHandler

#slaves = ["slave" + str(x) for x in range(0,10)]
#slave_ids = [x for x in range(1, 40)]
slave_ids = [25, 26]

LOG_WINDOW_HEIGHT = 10

# NTP_SERVER = "us.pool.ntp.org"
NTP_SERVER = "master-50.local"

BPM = 120
MEASURE = (4,4)
BEAT = 60/(BPM * (MEASURE[1]/4))
BAR = BEAT * MEASURE[0]
MAPPING_PATH = "mapping/"

def get_video(idx):
    # "/data/synctest.mp4"
    # return [f"/data/{idx}.jpg.mp4"]
    return [f"/data/{idx}.mp4"]

def render_log_window(stdscr, log):
    size = stdscr.getmaxyx()
    log_window_width = int(size[1]/2)

    try:
        for i, log_line in enumerate(log[-min(LOG_WINDOW_HEIGHT, size[0]):]):
            log_line = log_line[:size[1]]
            padding_len = log_window_width - len(log_line)
            stdscr.addstr(size[0] - LOG_WINDOW_HEIGHT + i, log_window_width, log_line + " " * padding_len)
    except:
        return

log = []
def append_log(log_str):
    global log
    log.append(str(log_str))
    log = log[-LOG_WINDOW_HEIGHT:]

ntp_client = ntplib.NTPClient()
time_diff = None
def update_time_diff():
    global time_diff
    ntp_response = ntp_client.request(NTP_SERVER, version=3)
    time_diff = time() - (ntp_response.tx_time + ntp_response.delay/2)
    append_log(f"diff: {time_diff} delay:{ntp_response.delay/2}")

def get_server_time():
    if time_diff is None:
        return None

    return time() - time_diff

def connect_mqtt():
    def on_connect(client, userdata, flags, rc):
        if rc == 0:
            append_log("Connected to MQTT Broker!")
            client.subscribe("/s/#")
            keepalive_cnt = 0
            update_time_diff()
        else:
            append_log("Failed to connect, return code %d\n" % rc)

    def on_disconnect(client, userdata, rc):
        append_log("disconnected from MQTT Broker!")

    client = paho.mqtt.client.Client(client_id=None, clean_session=True, userdata=None, protocol=mqtt.MQTTv311, transport="tcp")
    client.on_connect = on_connect
    client.on_disconnect = on_disconnect
    client.reconnect_delay_set(min_delay=1, max_delay=2)
    
    def mqtt_loop():
        while True:
            try:
                client.connect("master-50.local", port=1883, keepalive=2)
                break
            except Exception as e:
                append_log(e)
                sleep(2)
        client.loop_forever()

    
    t = threading.Thread(target=mqtt_loop)
    t.daemon = True # stop if the program exits
    t.start()

    return client


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

def draw_slave(stdscr, slave, idx, server_time):
    size = stdscr.getmaxyx()
    unwrap_y = idx * SLAVE_LINES
    size_y = size[0] - LOG_WINDOW_HEIGHT - 1
    y = int(unwrap_y % size_y)
    x = int(unwrap_y / size_y) * int(size[1]/4)

    for i in range(SLAVE_LINES):
        stdscr.addstr(y + i, x, " " * int(size[1]/4))

    slave.update(stdscr, x, y, server_time)

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
    curses.init_pair(7, curses.COLOR_BLUE, curses.COLOR_BLACK)

    client = connect_mqtt()

    slaves = [SlaveHandler(client, x, append_log) for x in slave_ids]
    for slave in slaves:
        try:
            f = open(MAPPING_PATH + str(slave.get_idx()) + ".map", "r")
            s = f.read()
            s = json.loads(s)
            # append_log(s)
            slave.set_mapping(s)
        except Exception as e:
            append_log(e)

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

        else:
            if move:
                slaves[idx].set_position(corner, x)
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

        server_time = get_server_time()
        for i, slave in enumerate(slaves):
            draw_slave(stdscr, slave, i, server_time)

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

            elif char == ord('\n'):
                append_log("saving mapping")
                for slave in slaves:
                    try:
                        f = open(MAPPING_PATH + str(slave.get_idx()) + ".map", "w")
                        f.write(json.dumps(slave.get_mapping()))
                    except Exception as e:
                        append_log(e)

            elif char == ord('t'):
                append_log("start sync time")
                apply_slave(select_slave, lambda x: x.sync_time(NTP_SERVER))

            elif char == ord('r'):
                append_log("run omx")
                if select_slave is None:
                    for slave in slaves:
                        slave.run(get_video(slave.get_idx()))
                else:
                    slaves[select_slave].run(get_video(slaves[select_slave].get_idx()))

            elif char == ord('o'):
                append_log("play")
                # apply_slave(select_slave, lambda x: x.play())
                # TODO get time from centeral NTP
                server_time = get_server_time()
                if server_time is not None:
                    apply_slave(select_slave, lambda x: x.schedule(server_time + 2))

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