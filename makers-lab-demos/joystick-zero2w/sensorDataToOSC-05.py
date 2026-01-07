'''
sensorDataToOSC-05.py  (SSD1306 version, edge-only button, 3-line OLED, shutdown->PD mute)
Raspberry Pi Zero 2 W
---------------------------------
- Reads joystick X/Y (MCP3008 CH0/CH1)
- Reads 10 k pot (MCP3008 CH2)
- Reads joystick button on GPIO 5 (active-low, debounced)
- Sends normalized data via OSC → Pure Data (port 8000)
    - /joystick/x  (float 0.0–1.0)
    - /joystick/y  (float 0.0–1.0)
    - /pot         (float 0.0–1.0)
    - /button      (int 0/1)  SENT ONLY ON EDGE CHANGES
    - /shutdown    (int 1)    sent right before system shutdown
- Receives patch/performer name via OSC ← Pure Data (/student on port 9000)
- OLED (128x32) layout:
    Line 1: patch name
    Line 2: joystick x/y
    Line 3: pot + button
- Hold joystick button for HOLD_TO_SHUTDOWN seconds to shutdown (uses sudo -n)
- Handles SIGTERM/SIGINT for clean systemd stop
- Cleanup on exit (stop OSC server, clear OLED, deinit pins)
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

def handle_termination(signum, frame):
    global running
    running = False

signal.signal(signal.SIGTERM, handle_termination)
signal.signal(signal.SIGINT, handle_termination)

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
# OSC ← Pure Data (patch name)
# ------------------------
LISTEN_PORT = 9000
current_patch_name = "Patch: (none)"
name_lock = threading.Lock()

def student_handler(address, *args):
    global current_patch_name
    if args:
        with name_lock:
            current_patch_name = str(args[0])
        print("received name: %s" % current_patch_name)

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

def draw_main_screen(patch_name, x_val, y_val, pot_val, btn_state):
    oled.fill(0)
    oled.text(patch_name[:20], 0, 0, 1)
    oled.text("x:%4.2f y:%4.2f" % (x_val, y_val), 0, 8, 1)
    oled.text("p:%4.2f b:%d" % (pot_val, btn_state), 0, 16, 1)
    oled.show()

def request_shutdown():
    # Tell PD to mute immediately (your patch routes "shutdown 1")
    try:
        osc.send_message("/shutdown", 1)
        time.sleep(0.05)
    except Exception:
        pass

    # Run shutdown with sudo (non-interactive). Must succeed without password prompt.
    result = subprocess.run(
        ["/usr/bin/sudo", "-n", "/sbin/shutdown", "-h", "now"],
        capture_output=True,
        text=True,
        check=False
    )

    if result.returncode != 0:
        try:
            oled.fill(0)
            oled.text("shutdown failed", 0, 0, 1)
            oled.text("rc:%d" % result.returncode, 0, 16, 1)
            oled.show()
        except Exception:
            pass

        print("shutdown failed rc=%d stderr=%s" % (result.returncode, result.stderr.strip()))
        time.sleep(2.0)

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

# Only send /button on edge changes
last_sent_btn_state = None

try:
    while running:
        # --- read analog values ---
        x_val = norm(chan_x.value)
        y_val = norm(chan_y.value)
        pot_val = norm(chan_pot.value)

        # --- read button (debounced edges) ---
        btn_event = read_button()
        btn_state = 1 if last_button_state else 0

        # --- hold-to-shutdown logic ---
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
                time.sleep(0.2)

                request_shutdown()
                running = False
                continue

        # --- send OSC to PD (continuous) ---
        osc.send_message("/joystick/x", x_val)
        osc.send_message("/joystick/y", y_val)
        osc.send_message("/pot", pot_val)

        # --- send /button only on changes (edges) ---
        if btn_event is not None:
            send_val = 1 if btn_event else 0
            if send_val != last_sent_btn_state:
                osc.send_message("/button", send_val)
                last_sent_btn_state = send_val

        # --- update OLED (always) ---
        with name_lock:
            patch_name = current_patch_name
        draw_main_screen(patch_name, x_val, y_val, pot_val, btn_state)

        # optional debug print
        print("x:%.3f y:%.3f p:%.3f b:%d" % (x_val, y_val, pot_val, btn_state))
        time.sleep(0.1)

finally:
    cleanup()
