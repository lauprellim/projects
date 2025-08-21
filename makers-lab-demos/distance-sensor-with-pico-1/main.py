"""
Micropython program for Raspberry Pi Pico W
- Reads distance from HC-SR04
- Uses a button to cycle through students' OSC modes
- Reads a potentiometer for volume control
- Sends data over UDP to Pd

Use a 10 or 100 kohm linear potentiometer. Remember to wire 3.3V -> outer lug,
ground to other outer lug, and wiper goes to Pico ADC (ADC 26 in this case).
You can wire a small RC filter on the wiper for steader readings, but
that's not necessary. If you want add a 0.1uF capacitor from wiper to ground.

Don't send 5V to the wiper because the pico's ADC is only 3.3V.
"""

import network
import socket
import struct
import time
from machine import Pin, ADC

# === WiFi Setup ===
SSID = "YOUR_WIFI_SSID"
PASSWORD = "YOUR_WIFI_PASSWORD"
UDP_IP = "192.168.1.100"   # IP of computer running PD
UDP_PORT = 8000            # Port PD is listening on

# === Hardware Setup ===
trigger = Pin(17, Pin.OUT)
echo = Pin(16, Pin.IN)
button = Pin(14, Pin.IN, Pin.PULL_UP)
pot = ADC(26)  # Potentiometer connected to GP26 (ADC0)

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
            msg += struct.pack(">f", arg)  # float
        elif t == "i":
            msg += struct.pack(">i", arg)  # int
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

# === Modes ===
modes = ["/distance/freq", "/distance/filter1", "/distance/filter2"]
current_mode = 0
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
    # speed of sound is 343 m/sec which is 0.0343 cm/usec
    # if round trip duration is 1164 us half is 582 us,
    # 21.9 microseconds per cm
    # So your duration gets divided by 29.1 = 20 cm away
    distance = (duration / 2) / 29.1
    return distance

def read_volume():
    # Pico is 12-bit ADC but these values get left-shifted
    # 4 bits to the right so they look like 16 bit value
    raw = pot.read_u16()
    return raw / 65535.0  # scale to 0.0–1.0

# === Main Loop ===
while True:
    # Debounced button check
    if button.value() == 0:
        now = time.ticks_ms()
        if (now - last_button_time) > (debounce_delay * 1000):
            current_mode = (current_mode + 1) % len(modes)
            print("Switched mode:", modes[current_mode])
            last_button_time = now

    dist = read_distance()
    vol = read_volume()

    # Build OSC message with two floats: [distance, volume]
    msg = build_osc_message(modes[current_mode], "ff", [dist, vol])
    sock.sendto(msg, (UDP_IP, UDP_PORT))

    print("Sent:", modes[current_mode], "dist=%.2f cm vol=%.2f" % (dist, vol))
    time.sleep(0.1)
