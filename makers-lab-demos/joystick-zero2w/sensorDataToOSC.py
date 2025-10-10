'''
sensorDataToOSC.py

Bidirectional OSC Bridge
Raspberry Pi Zero 2 W  |  MCP3008 + Joystick + LCD (PCF8574)

→ Sends normalized sensor data to Pure Data:
    /joystick/x   float
    /joystick/y   float
    /pot          float
    /button       int (0/1)

← Receives performer name from Pure Data:
    /student "Name"

Displays both live data and performer names on 16×2 LCD
'''

import time
import threading
import board
import busio
import digitalio
from RPLCD.i2c import CharLCD
import adafruit_mcp3xxx.mcp3008 as MCP
from adafruit_mcp3xxx.analog_in import AnalogIn
from pythonosc.udp_client import SimpleUDPClient
from pythonosc import dispatcher, osc_server

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
# Joystick button  (GPIO5)
# ------------------------
button_pin = digitalio.DigitalInOut(board.D5)
button_pin.direction = digitalio.Direction.INPUT
button_pin.pull = digitalio.Pull.UP

last_button_state = False
last_debounce_time = 0
DEBOUNCE_DELAY = 0.05  # seconds

def read_button():
    # Return True (pressed) or False (released) when stable, else None
    global last_button_state, last_debounce_time
    current_state = not button_pin.value  # active-low
    now = time.monotonic()
    if current_state != last_button_state and (now - last_debounce_time) > DEBOUNCE_DELAY:
        last_debounce_time = now
        last_button_state = current_state
        return current_state
    return None

# ------------------------
# LCD  (PCF8574)
# ------------------------
lcd = CharLCD('PCF8574', address=0x27, port=1, cols=16, rows=2)
lcd.clear()
lcd.write_string("Initializing...\n")

# ------------------------
# OSC client → Pure Data
# ------------------------
PD_IP   = "127.0.0.1"
PD_PORT = 8000
osc = SimpleUDPClient(PD_IP, PD_PORT)

# ------------------------
# OSC server ← Pure Data
# ------------------------
LISTEN_PORT = 9000
student_name = None
name_lock = threading.Lock()
name_display_time = 1.5  # seconds

def student_handler(address, *args):
    global student_name
    if args:
        with name_lock:
            student_name = str(args[0])
        print(f"Received name: {student_name}")

disp = dispatcher.Dispatcher()
disp.map("/student", student_handler)
server = osc_server.ThreadingOSCUDPServer(("0.0.0.0", LISTEN_PORT), disp)
threading.Thread(target=server.serve_forever, daemon=True).start()
print(f"Listening for /student on UDP port {LISTEN_PORT}")

# ------------------------
# Helper functions
# ------------------------
def norm(val):
    return round(val / 65535.0, 4)

'''
def show_name_on_lcd(name):
    lcd.clear()
    lcd.write_string("Now playing:\n")
    lcd.write_string(name[:16])
    time.sleep(name_display_time)
    lcd.clear()
'''

def show_name_on_lcd(name):
	lcd.clear()
	lcd.home()   # move cursor to top-left corner
	lcd.write_string("Now playing:")
	lcd.cursor_pos=(1,0)  # second line
	lcd.write_string(name[:16]) # truncate
	time.sleep(name_display_time)
	lcd.clear()

# ------------------------
# Main loop
# ------------------------
try:
    while True:
        # check if new student name has arrived
        with name_lock:
            current_name = student_name
            student_name = None
        if current_name:
            show_name_on_lcd(current_name)

        # --- Read analog inputs ---
        x_val = norm(chan_x.value)
        y_val = norm(chan_y.value)
        pot_val = norm(chan_pot.value)

        # --- Read button (debounced) ---
        btn_event = read_button()
        btn_state = 1 if last_button_state else 0

        # --- Send OSC messages ---
        osc.send_message("/joystick/x", x_val)
        osc.send_message("/joystick/y", y_val)
        osc.send_message("/pot", pot_val)
        osc.send_message("/button", btn_state)

        # --- Update LCD (live data) ---
        lcd.cursor_pos = (0, 0)
        lcd.write_string(f"x:{x_val:4.2f} y:{y_val:4.2f}   ")
        lcd.cursor_pos = (1, 0)
        lcd.write_string(f"volume:{pot_val:4.2f}  ")

        # optional debug print
        print(f"x:{x_val:.3f} y:{y_val:.3f} p:{pot_val:.3f} b:{btn_state}")

        time.sleep(0.01)

except KeyboardInterrupt:
    lcd.clear()
    lcd.write_string("Goodbye!")
    time.sleep(1)
    lcd.clear()
