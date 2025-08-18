'''
Micropython script for Raspberry Pi Pico W to:
- Connect to Wi-Fi
- Read HC-SR04 ultrasonic sensor
- Read button state
- Send OSC message over UDP to a PD patch when button is pressed
'''

import network
import socket
import time
import struct
from machine import Pin

# --------------------
# USER CONFIG
# --------------------
SSID = "NETGEAR75"
PASSWORD = "modernmoon901"
PD_IP = "192.168.1.2"   # IP address of computer running Pure Data
PD_PORT = 9000            # UDP port PD is listening on
OSC_ADDRESS = "/distance" # OSC message address

# --------------------
# HARDWARE SETUP
# --------------------
TRIG_PIN = 17    # GP3 for HC-SR04 trigger
ECHO_PIN = 16    # GP2 for HC-SR04 echo
BUTTON_PIN = 14 # GP15 for button (active low)

trig = Pin(TRIG_PIN, Pin.OUT)
echo = Pin(ECHO_PIN, Pin.IN)
button = Pin(BUTTON_PIN, Pin.IN, Pin.PULL_UP)

# --------------------
# FUNCTIONS
# --------------------
def connect_wifi():
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    wlan.connect(SSID, PASSWORD)
    print("Connecting to Wi-Fi...", end="")
    while not wlan.isconnected():
        print(".", end="")
        time.sleep(0.5)
    print("\nConnected:", wlan.ifconfig())
    return wlan

def measure_distance():
    # Send a 10µs pulse
    trig.low()
    time.sleep_us(2)
    trig.high()
    time.sleep_us(10)
    trig.low()

    # Measure echo time
    while echo.value() == 0:
        start = time.ticks_us()
    while echo.value() == 1:
        end = time.ticks_us()

    duration = time.ticks_diff(end, start)
    distance_cm = (duration / 2) / 29.1  # convert to cm
    return distance_cm

def pad_osc_string(s):
    # Pad OSC string to multiple of 4 bytes
    s_bytes = s.encode('utf-8') + b'\x00'
    while len(s_bytes) % 4 != 0:
        s_bytes += b'\x00'
    return s_bytes

def build_osc_message(address, value):
    # OSC format: address, type tag, value
    addr_bytes = pad_osc_string(address)
    type_bytes = pad_osc_string(",f")  # single float
    value_bytes = struct.pack(">f", value)  # big-endian float
    return addr_bytes + type_bytes + value_bytes

# --------------------
# MAIN PROGRAM
# --------------------
wlan = connect_wifi()
udp = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

try:
    while True:
        if button.value() == 0:  # button pressed
            dist = measure_distance()
            msg = build_osc_message(OSC_ADDRESS, dist)
            # send!
            udp.sendto(msg, (PD_IP, PD_PORT))
            print("Distance:", dist, "cm")
        time.sleep(0.1)
except KeyboardInterrupt:
    udp.close()
    wlan.active(False)