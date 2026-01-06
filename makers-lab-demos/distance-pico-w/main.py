"""
Micropython program for Raspberry Pi Pico W
  Reads distance from HC-SR04
  Sends distance (cm), pot value, button press, and device ID over UDP to Pd
  The data is sent as OSC
  Pd handles all mode switching logic

OLED (128x32 I2C, SSD1306 / Adafruit #4440):
  Line 0: ID:<boxID> WiFi:<OK/down>
  Line 1: (blank)
  Line 2: <distance> cm
  Line 3: B:<0/1> V:<0.00>

Button semantics:
  pressed  -> 1
  released -> 0
  (This semantic value is sent over OSC and displayed on OLED.)
"""

import network
import socket
import struct
import time
from machine import Pin, ADC, I2C
import ssd1306

# ----------------------------
# Configuration
# ----------------------------

SSID = "NETGEAR75"
PASSWORD = "modernmoon901"

UDP_IP = "192.168.1.6"   # IP address of computer running Pure Data
UDP_PORT = 9000          # UDP port PD is listening on

BOX_ID = 20              # stable identifier for this unit

# Pins (as in your original script)
trigger = Pin(17, Pin.OUT)
echo = Pin(16, Pin.IN)

button = Pin(14, Pin.IN, Pin.PULL_UP)  # electrically: pressed->0, released->1
pot = ADC(26)

# OLED (adjust pins/address here if needed)
OLED_WIDTH = 128
OLED_HEIGHT = 32
OLED_ADDR = 0x3C
i2c = I2C(0, sda=Pin(0), scl=Pin(1), freq=400000)
oled = ssd1306.SSD1306_I2C(OLED_WIDTH, OLED_HEIGHT, i2c, addr=OLED_ADDR)

# Debounce
debounce_delay_s = 0.30
last_pressed = 0
last_button_time_ms = 0

# ----------------------------
# OSC helper functions
# ----------------------------

def pad_osc_string(s):
    b = s.encode("utf-8") + b"\x00"
    while (len(b) % 4) != 0:
        b += b"\x00"
    return b

def build_osc_message(address, types, args):
    msg = pad_osc_string(address)
    msg += pad_osc_string("," + types)

    for t, arg in zip(types, args):
        if t == "f":
            msg += struct.pack(">f", float(arg))
        elif t == "i":
            msg += struct.pack(">i", int(arg))
    return msg

# ----------------------------
# Hardware read functions
# ----------------------------

def read_distance(timeout_us=30000):
    """
    Returns distance in cm (float), or None on timeout.
    """
    trigger.low()
    time.sleep_us(2)
    trigger.high()
    time.sleep_us(10)
    trigger.low()

    # wait for echo to go high
    t0 = time.ticks_us()
    while echo.value() == 0:
        if time.ticks_diff(time.ticks_us(), t0) > timeout_us:
            return None

    start = time.ticks_us()

    # wait for echo to go low
    while echo.value() == 1:
        if time.ticks_diff(time.ticks_us(), start) > timeout_us:
            return None

    end = time.ticks_us()
    duration = time.ticks_diff(end, start)

    # convert to cm: cm = (us/2)/29.1 (approx)
    return (duration / 2.0) / 29.1

def read_volume():
    raw = pot.read_u16()
    return 1.0 - (raw / 65535.0)

def read_pressed_semantic():
    """
    Returns semantic pressed state:
      physically pressed   -> 1
      physically released  -> 0
    """
    return 1 if button.value() == 0 else 0

# ----------------------------
# OLED update
# ----------------------------

def update_oled(dist_cm, vol, pressed, wifi_ok):
    wf_txt = "OK" if wifi_ok else "down"

    # Line 0: ID + WiFi
    # Keep it short for 16-char width; remove extra spaces if needed.
    line0 = "ID:%d WiFi:%s" % (BOX_ID, wf_txt)

    # Line 1: blank
    line1 = ""

    # Line 2: distance only
    if dist_cm is None:
        line2 = "---.- cm"
    else:
        line2 = "%.1f cm" % dist_cm

    # Line 3: button + volume
    line3 = "B:%d V:%.2f" % (pressed, vol)

    oled.fill(0)
    oled.text(line0[:16], 0, 0)
    oled.text(line1[:16], 0, 8)
    oled.text(line2[:16], 0, 16)
    oled.text(line3[:16], 0, 24)
    oled.show()

# ----------------------------
# Networking setup
# ----------------------------

wlan = network.WLAN(network.STA_IF)
wlan.active(True)
wlan.connect(SSID, PASSWORD)

# show OLED while connecting (up to a timeout)
wifi_timeout_s = 15
t_start_ms = time.ticks_ms()

while (not wlan.isconnected()) and (time.ticks_diff(time.ticks_ms(), t_start_ms) < wifi_timeout_s * 1000):
    update_oled(None, 0.0, read_pressed_semantic(), False)
    time.sleep(0.2)

if wlan.isconnected():
    print("Connected:", wlan.ifconfig())
else:
    print("WiFi not connected (continuing anyway).")

sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

# ----------------------------
# Main loop
# ----------------------------

while True:
    dist = read_distance()
    vol = read_volume()
    pressed = read_pressed_semantic()
    wifi_ok = wlan.isconnected()

    # Send device identifier every loop
    msg_id = build_osc_message("/boxID", "i", [BOX_ID])
    sock.sendto(msg_id, (UDP_IP, UDP_PORT))

    # Send distance + pot every loop
    dist_to_send = dist if (dist is not None) else 0.0
    msg_dist = build_osc_message("/distanceCM", "f", [dist_to_send])
    msg_vol = build_osc_message("/pot", "f", [vol])
    sock.sendto(msg_dist, (UDP_IP, UDP_PORT))
    sock.sendto(msg_vol, (UDP_IP, UDP_PORT))

    # Send button changes (debounced), using semantic pressed bit
    now_ms = time.ticks_ms()
    if (pressed != last_pressed) and (time.ticks_diff(now_ms, last_button_time_ms) > int(debounce_delay_s * 1000)):
        last_button_time_ms = now_ms
        msg_btn = build_osc_message("/button", "i", [pressed])
        sock.sendto(msg_btn, (UDP_IP, UDP_PORT))
        last_pressed = pressed

    # Update OLED every loop
    update_oled(dist, vol, pressed, wifi_ok)

    time.sleep(0.1)

