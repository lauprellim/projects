# Written by Paul V. Miller
# Media Maker's Lab 2025 Project

import os
import time
import ssl
import wifi
import socketpool
import microcontroller
import adafruit_requests

import board
import busio
import adafruit_sht4x

#  connect to SSID
wifi.radio.connect(os.getenv('CIRCUITPY_WIFI_SSID'), os.getenv('CIRCUITPY_WIFI_PASSWORD'))

pool = socketpool.SocketPool(wifi.radio)
requests = adafruit_requests.Session(pool, ssl.create_default_context())

i2c = busio.I2C(scl=board.GP5, sda=board.GP4)
sht = adafruit_sht4x.SHT4x(i2c)

sht.mode = adafruit_sht4x.Mode.NOHEAT_HIGHPRECISION

while True:
    temp, hum = sht.measurements
    URLtemp = "%3.1f" %temp
    URLhum = "%3.1f" %hum
    formattedURL = "http://www.theoryofpaul.net/temphumid/enter-data.phtml?temp=" + str(URLtemp) + "&humidity=" + str(URLhum) + "&idLocations=2"
        
    response = requests.get(formattedURL)
    response.close()

    # 60 times 15 = 900 seconds
    time.sleep(900)
 