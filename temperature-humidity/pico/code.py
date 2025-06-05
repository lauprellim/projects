# Written by Paul V. Miller
# Media Maker's Lab 2025 Project
# Be sure to set the "idLocations" variable in the URL

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

# Initialize I2C and sensor
i2c = busio.I2C(scl=board.GP1, sda=board.GP0)
sht = adafruit_sht4x.SHT4x(i2c)
sht.mode = adafruit_sht4x.Mode.NOHEAT_HIGHPRECISION
# Let the sensor settle
time.sleep(1)

# Connect to WiFi
# print("Connecting to WiFi...")
wifi.radio.connect(os.getenv('CIRCUITPY_WIFI_SSID'), os.getenv('CIRCUITPY_WIFI_PASSWORD'))
# print("Connected to WiFi.")

# Prepare request session
pool = socketpool.SocketPool(wifi.radio)
requests = adafruit_requests.Session(pool, ssl.create_default_context())

# Main loop
while True:
    try:
        # Read sensor data
        temp, hum = sht.measurements
        URLtemp = "%3.1f" %temp
        URLhum = "%3.1f" %hum

        # Construct request URL
        formattedURL = (
            "http://www.theoryofpaul.net/temphumid-duq/enter-data.phtml?"
            f"temp={URLtemp}&humidity={URLhum}&idLocations=1&duqPassword=duQuesne1878!"
        )
        print(f"Sending data: Temp={URLtemp}°C, Humidity={URLhum}%")

        # Send GET request
        response = requests.get(formattedURL)
        response.close()
        # print("Data sent successfully.")

    except Exception as e:
        # print("Error occurred:", e)
        # Reset device if request failed
        microcontroller.reset()

    # Wait 15 minutes before next reading
    time.sleep(900)
