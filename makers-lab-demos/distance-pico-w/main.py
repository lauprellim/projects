"""
main.py

Pico W / Pico 2W application:
  - Reads distance from HC-SR04
  - Sends distance (cm), pot value, button press, and device ID over UDP as OSC
  - Updates SSD1306 OLED (128x32)

Robust boot behavior:
  - Waits briefly at boot so the OLED is ready on battery power
  - Retries OLED init
  - Logs boot progress and exceptions to boot-log.txt
  - Safe mode: hold button at boot to skip the main application
"""

import network
import socket
import struct
import time
import machine
from machine import Pin, ADC, I2C
import ssd1306

# ----------------------------
# Configuration
# ----------------------------

SSID = "NETGEAR75"
PASSWORD = "*********"

UDP_IP = "192.168.1.2"
UDP_PORT = 9000

BOX_ID = 30

# Pins
TRIG_PIN = 17
ECHO_PIN = 16
BUTTON_PIN = 15
POT_ADC = 26

# OLED
OLED_WIDTH = 128
OLED_HEIGHT = 32
OLED_ADDR = 0x3C
OLED_I2C_ID = 0
OLED_SDA = 0
OLED_SCL = 1
OLED_FREQ = 400000

# Debounce
debounce_delay_s = 0.30

# ----------------------------
# Logging
# ----------------------------

def log(msg):
    try:
        with open('boot-log.txt', 'a') as f:
            f.write('%d reset_cause=%d %s\n' % (time.time(), machine.reset_cause(), msg))
    except Exception:
        pass

# ----------------------------
# Boot pacing + safe mode
# ----------------------------

button = Pin(BUTTON_PIN, Pin.IN, Pin.PULL_UP)

time.sleep(1.5)  # critical: give OLED time to power up on battery boot
log('boot: entered main.py')

if button.value() == 0:
    log('boot: SAFE MODE (button held), skipping app')
    while True:
        time.sleep(1)

# ----------------------------
# Hardware setup (non-OLED)
# ----------------------------

trigger = Pin(TRIG_PIN, Pin.OUT)
echo = Pin(ECHO_PIN, Pin.IN)
pot = ADC(POT_ADC)

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
# Read functions
# ----------------------------

def read_distance(timeout_us=30000):
    trigger.low()
    time.sleep_us(2)
    trigger.high()
    time.sleep_us(10)
    trigger.low()

    t0 = time.ticks_us()
    while echo.value() == 0:
        if time.ticks_diff(time.ticks_us(), t0) > timeout_us:
            return None

    start = time.ticks_us()

    while echo.value() == 1:
        if time.ticks_diff(time.ticks_us(), start) > timeout_us:
            return None

    end = time.ticks_us()
    duration = time.ticks_diff(end, start)
    return (duration / 2.0) / 29.1

def read_volume():
    raw = pot.read_u16()
    return 1.0 - (raw / 65535.0)

def read_pressed_semantic():
    return 1 if button.value() == 0 else 0

# ----------------------------
# OLED init with retry
# ----------------------------

def init_oled(retries=5, delay_s=0.4):
    last_exc = None
    for k in range(retries):
        try:
            i2c = I2C(OLED_I2C_ID, sda=Pin(OLED_SDA), scl=Pin(OLED_SCL), freq=OLED_FREQ)
            addrs = i2c.scan()
            log('oled: i2c scan attempt %d: %s' % (k + 1, str(addrs)))

            oled = ssd1306.SSD1306_I2C(OLED_WIDTH, OLED_HEIGHT, i2c, addr=OLED_ADDR)
            oled.fill(0)
            oled.text('BOOTING...', 0, 0)
            oled.text('ID:%d' % BOX_ID, 0, 8)
            oled.show()
            log('oled: init OK')
            return oled
        except Exception as e:
            last_exc = e
            log('oled: init failed attempt %d: %r' % (k + 1, e))
            time.sleep(delay_s)

    raise last_exc

oled = init_oled()

def update_oled(dist_cm, vol, pressed, wifi_ok):
    wf_txt = "OK" if wifi_ok else "down"
    line0 = "ID:%d WiFi:%s" % (BOX_ID, wf_txt)
    line1 = ""
    if dist_cm is None:
        line2 = "---.- cm"
    else:
        line2 = "%.1f cm" % dist_cm
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

log('wifi: starting')
wlan = network.WLAN(network.STA_IF)
wlan.active(True)
wlan.connect(SSID, PASSWORD)

wifi_timeout_s = 15
t_start_ms = time.ticks_ms()

while (not wlan.isconnected()) and (time.ticks_diff(time.ticks_ms(), t_start_ms) < wifi_timeout_s * 1000):
    update_oled(None, 0.0, read_pressed_semantic(), False)
    time.sleep(0.2)

if wlan.isconnected():
    log('wifi: connected %s' % (str(wlan.ifconfig()),))
else:
    log('wifi: not connected (continuing)')

sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
log('udp: socket created')

# ----------------------------
# Main loop
# ----------------------------

log('loop: enter')

while True:
    dist = read_distance()
    vol = read_volume()
    pressed = read_pressed_semantic()
    wifi_ok = wlan.isconnected()

    msg_id = build_osc_message("/boxID", "i", [BOX_ID])
    sock.sendto(msg_id, (UDP_IP, UDP_PORT))

    dist_to_send = dist if (dist is not None) else 0.0
    msg_dist = build_osc_message("/distanceCM", "f", [dist_to_send])
    msg_vol = build_osc_message("/pot", "f", [vol])
    sock.sendto(msg_dist, (UDP_IP, UDP_PORT))
    sock.sendto(msg_vol, (UDP_IP, UDP_PORT))

    now_ms = time.ticks_ms()
    last_pressed, last_button_time_ms  # MicroPython allows this at module scope
    if (pressed != last_pressed) and (time.ticks_diff(now_ms, last_button_time_ms) > int(debounce_delay_s * 1000)):
        last_button_time_ms = now_ms
        msg_btn = build_osc_message("/button", "i", [pressed])
        sock.sendto(msg_btn, (UDP_IP, UDP_PORT))
        last_pressed = pressed

    update_oled(dist, vol, pressed, wifi_ok)
    time.sleep(0.1)
