"""
Micropython program for Raspberry Pi Pico W
- Reads distance from HC-SR04
- Sends distance (cm), pot value, button press, and device ID over UDP to Pd
- Pd handles all mode switching logic
"""

import network
import socket
import struct
import time
from machine import Pin, ADC

# === WiFi Setup ===
SSID = "NETGEAR75"
PASSWORD = "modernmoon901"
UDP_IP = "192.168.1.2"   # IP address of computer running Pure Data
UDP_PORT = 9000          # UDP port PD is listening on

# === Device Identifier ===
BOX_ID = 10  # Unique identifier for this device (change per unit)

# === Hardware Setup ===
trigger = Pin(17, Pin.OUT)
echo = Pin(16, Pin.IN)
button = Pin(14, Pin.IN, Pin.PULL_UP)
pot = ADC(26)

# === OSC Helper Functions ===
def pad_osc_string(s: str) -> bytes:
    b = s.encode("utf-8") + b"\x00"
    while len(b) % 4 != 0:
        b += b"\x00"
    return b

def build_osc_message(address: str, types: str, args: list) -> bytes:
    msg = pad_osc_string(address)
    msg += pad_osc_string("," + types)
    for t, arg in zip(types, args):
        if t == "f":
            msg += struct.pack(">f", arg)
        elif t == "i":
            msg += struct.pack(">i", arg)
    return msg

# === Networking ===
wlan = network.WLAN(network.STA_IF)
wlan.active(True)
wlan.connect(SSID, PASSWORD)
while not wlan.isconnected():
    print("Connecting to WiFi...")
    time.sleep(1)
print("Connected:", wlan.ifconfig())

sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

# === Button State Tracking ===
last_button_state = 1
last_button_time = 0
debounce_delay = 0.3

# === Functions ===
def read_distance():
    trigger.low()
    time.sleep_us(2)
    trigger.high()
    time.sleep_us(10)
    trigger.low()

    while echo.value() == 0:
        pass
    start = time.ticks_us()
    while echo.value() == 1:
        pass
    end = time.ticks_us()

    duration = time.ticks_diff(end, start)
    distance = (duration / 2) / 29.1  # convert to cm
    return distance

def read_volume():
    raw = pot.read_u16()
    return raw / 65535.0  # scale 0–1

# === Main Loop ===
while True:
    dist = read_distance()
    vol = read_volume()

    # Send device identifier once per loop (or could send every N loops)
    msg_id = build_osc_message("/boxID", "i", [BOX_ID])
    sock.sendto(msg_id, (UDP_IP, UDP_PORT))

    # Send distance and pot values
    msg_dist = build_osc_message("/distanceCM", "f", [dist])
    msg_vol = build_osc_message("/pot", "f", [vol])
    sock.sendto(msg_dist, (UDP_IP, UDP_PORT))
    sock.sendto(msg_vol, (UDP_IP, UDP_PORT))

    # Debounced button handling
    state = button.value()
    now = time.ticks_ms()
    if state != last_button_state and (now - last_button_time) > (debounce_delay * 1000):
        last_button_time = now
        if state == 0:  # pressed
            msg_btn = build_osc_message("/button", "i", [1])
            sock.sendto(msg_btn, (UDP_IP, UDP_PORT))
            # print("Button pressed")
        else:  # released
            msg_btn = build_osc_message("/button", "i", [0])
            sock.sendto(msg_btn, (UDP_IP, UDP_PORT))
            # print("Button released")
        last_button_state = state

    # for printing to the console, debugging:
    # print("Sent boxID=%d  dist=%.2f cm  vol=%.2f" % (BOX_ID, dist, vol))
    time.sleep(0.1)
