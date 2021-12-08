import curses
from time import sleep, time
# from curses.textpad import Textbox, rectangle

slaves = ["slave" + str(x) for x in range(0,10)]

# rectangle(stdscr, 1,0, 1+5+1, 1+30+1)

# def append_log(log):

LOG_WINDOW_HEIGHT = 10
LOG_BASE_LINE = 0

def render_log_window(stdscr, log):
    size = stdscr.getmaxyx()

    for i, log_line in enumerate(log[-min(LOG_WINDOW_HEIGHT, size[0]):]):
        log_line = log_line[:size[1]]
        padding_len = len(log_line)
        stdscr.addstr(LOG_BASE_LINE + i, 0, log_line + " " * padding_len)

log = []
def append_log(stdscr, log_str):
    global log
    log.append(str(log_str))
    log = log[-LOG_WINDOW_HEIGHT:]
    render_log_window(stdscr, log)

BPM = 120
MEASURE = (4,4)
BEAT = 60/(BPM * (MEASURE[1]/4))
BAR = BEAT * MEASURE[0]

def draw_beat(stdscr, measure):
    size = stdscr.getmaxyx()

    color = curses.color_pair(2) if int(measure) == 0 else curses.color_pair(1)
    for y in range(3, 6):
        for x in range (0, 5):
            stdscr.move(size[0] - y, x)
            if measure % 1 < 0.15:
                stdscr.addch(curses.ACS_BOARD, color)
            else:
                stdscr.addch(" ")
    stdscr.addstr(size[0] - 4, 1, f"{int(measure) + 1}/{MEASURE[1]}")
    stdscr.move(0, 0)

def c_main(stdscr):
    stdscr.nodelay(True)
    curses.init_pair(1, curses.COLOR_YELLOW, curses.COLOR_BLACK)
    curses.init_pair(2, curses.COLOR_RED, curses.COLOR_BLACK)
    
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
        stdscr.addstr(size[0] - 2, 0, f"{BPM} BPM {MEASURE[0]}/{MEASURE[1]} (x,y): {size}")

        measure = (song_duration/BEAT) % MEASURE[0]
        
        draw_beat(stdscr, measure)

        char = stdscr.getch()
        if char > 0:
            if char == ord(' '):
                current_bar = int(song_duration / BAR)
                start_time = time() - current_bar * BAR
            elif char == curses.KEY_LEFT:
                start_time += 1/BEAT
            elif char == curses.KEY_RIGHT:
                start_time -= 1/BEAT

            append_log(stdscr, f"you pressed {str(char)}")
        
    return 0

# stdscr.refresh()

def main():
    return curses.wrapper(c_main)


if __name__ == '__main__':
    exit(main())