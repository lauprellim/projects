'''
sensorDataToOSC-04.py  (SSD1306 version, hold-to-shutdown + graceful cleanup + SIGTERM)
Raspberry Pi Zero 2 W
---------------------------------
- Reads joystick X/Y (MCP3008 CH0/CH1)
- Reads 10 k pot (MCP3008 CH2)
- Reads joystick button on GPIO 5 (active-low, debounced)
- Sends normalized data via OSC → Pure Data (port 8000)
- Receives performer name via OSC ← Pure Data (/student on port 9000)
- Displays live sensor data or performer name on a 128x32 SSD1306 OLED (I2C)
- If user holds joystick button for HOLD_TO_SHUTDOWN seconds, requests system shutdown
- Always performs cleanup on exit (stop OSC server, clear OLED, deinit pins)
- Handles SIGTERM so systemd can stop it cleanly
'''

import time
import threading
import subprocess
import signal

import board
import busio
import digitalio

import adafruit_mcp3xxx.mcp3008 as MCP
from adafruit_mcp3xxx.analog_in import AnalogIn

from pythonosc.udp_client import SimpleUDPClient
from pythonosc import dispatcher, osc_server

import adafruit_ssd1306

# ------------------------
# Global run flag (for clean exit)
# ------------------------
running = True

def handle_sigterm(signum, frame):
    global running
    running = False

signal.signal(signal.SIGTERM, handle_sigterm)
signal.signal(signal.SIGINT, handle_sigterm)

# ------------------------
# SPI  (MCP3008)
# ------------------------
spi = busio.SPI(clock=board.SCK, MISO=board.MISO, MOSI=board.MOSI)
cs  = digitalio.DigitalInOut(board.CE0)
mcp = MCP.MCP3008(spi, cs)

chan_x   = AnalogIn(mcp, MCP.P0)
chan_y   = AnalogIn(mcp, MCP.P1)
chan_pot = AnalogIn(mcp, MCP.P2)

# ------------------------
# Joystick button  (GPIO 5)
# ------------------------
button_pin = digitalio.DigitalInOut(board.D5)
button_pin.direction = digitalio.Direction.INPUT
button_pin.pull = digitalio.Pull.UP

last_button_state = False
last_debounce_time = 0.0
DEBOUNCE_DELAY = 0.05  # seconds

def read_button():
    """Return True (pressed) or False (released) when stable, else None."""
    global last_button_state, last_debounce_time
    current_state = not button_pin.value  # active-low
    now = time.monotonic()
    if current_state != last_button_state and (now - last_debounce_time) > DEBOUNCE_DELAY:
        last_debounce_time = now
        last_button_state = current_state
        return current_state
    return None

# ------------------------
# I2C + SSD1306 OLED (128x32)
# ------------------------
i2c = busio.I2C(board.SCL, board.SDA)
oled_width = 128
oled_height = 32
oled = adafruit_ssd1306.SSD1306_I2C(oled_width, oled_height, i2c, addr=0x3C)

oled.fill(0)
oled.text("initializing...", 0, 0, 1)
oled.show()
time.sleep(1)

# ------------------------
# OSC → Pure Data
# ------------------------
PD_IP   = "127.0.0.1"
PD_PORT = 8000
osc = SimpleUDPClient(PD_IP, PD_PORT)

# ------------------------
# OSC ← Pure Data
# ------------------------
LISTEN_PORT = 9000
student_name = None
name_lock = threading.Lock()
name_display_time = 2.0  # seconds

def student_handler(address, *args):
    global student_name
    if args:
        with name_lock:
            student_name = str(args[0])
        print("received name: %s" % student_name)

disp = dispatcher.Dispatcher()
disp.map("/student", student_handler)

server = osc_server.ThreadingOSCUDPServer(("0.0.0.0", LISTEN_PORT), disp)
threading.Thread(target=server.serve_forever, daemon=True).start()
print("listening for /student on UDP port %d" % LISTEN_PORT)

# ------------------------
# Helpers
# ------------------------
def norm(val):  # 0–65535 → 0.0–1.0
    return round(val / 65535.0, 4)

def request_shutdown():
    subprocess.run(["/sbin/shutdown", "-h", "now"], check=False)

def draw_main_screen(x_val, y_val, pot_val, btn_state):
    oled.fill(0)
    oled.text("x:%4.2f" % x_val, 0, 0, 1)
    oled.text("y:%4.2f" % y_val, 64, 0, 1)
    oled.text("p:%4.2f" % pot_val, 0, 16, 1)
    oled.text("b:%d" % btn_state, 64, 16, 1)
    oled.show()

def show_name_on_oled(name):
    oled.fill(0)
    oled.text("Patch:", 0, 0, 1)
    oled.text(name[:20], 0, 16, 1)
    oled.show()
    time.sleep(name_display_time)

def cleanup():
    try:
        server.shutdown()
        server.server_close()
    except Exception:
        pass

    try:
        oled.fill(0)
        oled.show()
    except Exception:
        pass

    try:
        button_pin.deinit()
    except Exception:
        pass

    try:
        cs.deinit()
    except Exception:
        pass

# ------------------------
# Main loop
# ------------------------
HOLD_TO_SHUTDOWN = 4.0  # seconds
press_start_time = None
shutdown_armed = False

try:
    name_timer = 0.0

    while running:
        x_val = norm(chan_x.value)
        y_val = norm(chan_y.value)
        pot_val = norm(chan_pot.value)

        btn_event = read_button()
        btn_state = 1 if last_button_state else 0

        now = time.monotonic()

        if btn_event is True:
            press_start_time = now
            shutdown_armed = True
        elif btn_event is False:
            press_start_time = None
            shutdown_armed = False

        if shutdown_armed and last_button_state and press_start_time is not None:
            if (now - press_start_time) >= HOLD_TO_SHUTDOWN:
                oled.fill(0)
                oled.text("Shutting down...", 0, 0, 1)
                oled.show()
                time.sleep(0.5)

                request_shutdown()
                running = False
                continue

        osc.send_message("/joystick/x", x_val)
        osc.send_message("/joystick/y", y_val)
        osc.send_message("/pot", pot_val)
        osc.send_message("/button", btn_state)

        with name_lock:
            current_name = student_name
            student_name = None
        if current_name:
            show_name_on_oled(current_name)
            name_timer = time.monotonic() + name_display_time

        if time.monotonic() > name_timer:
            draw_main_screen(x_val, y_val, pot_val, btn_state)

        print("x:%.3f y:%.3f p:%.3f b:%d" % (x_val, y_val, pot_val, btn_state))

        time.sleep(0.1)

finally:
    cleanup()
