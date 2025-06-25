# Written by Paul V. Miller
# Media Maker's Lab 2025 Project
# Be sure to set the "idLocations" variable in the URL

import os
import time
import ssl
import wifi
import socketpool
# import machine # microcontroller is not available in circuitpython?
# then in place of microcontroller.reset(), use machine.reset()
import microcontroller
import adafruit_requests

import board
import busio
import adafruit_sht4x

# Initialize I2C and sensor
i2c = busio.I2C(scl=board.GP1, sda=board.GP0)
sht = adafruit_sht4x.SHT4x(i2c)
sht.mode = adafruit_sht4x.Mode.NOHEAT_HIGHPRECISION
time.sleep(1)  # Let the sensor settle

# Connect to WiFi
wifi.radio.connect(os.getenv('CIRCUITPY_WIFI_SSID'), os.getenv('CIRCUITPY_WIFI_PASSWORD'))

# Prepare request session
pool = socketpool.SocketPool(wifi.radio)
requests = adafruit_requests.Session(pool, ssl.create_default_context())

# Main loop
while True:
    try:
        # Read sensor data
        temp, hum = sht.measurements
        URLtemp = "%3.1f" % temp
        URLhum = "%3.1f" % hum

        # Construct request URL
        formattedURL = (
            "http://www.theoryofpaul.net/temphumid-duq/enter-data.phtml?"
            f"temp={URLtemp}&humidity={URLhum}&idLocations=3&duqPassword=duQuesne1878!"
        )

        # Try up to 3 times to send data
        maxRetries = 3
        for attempt in range(maxRetries):
            try:
                response = requests.get(formattedURL)
                response.close()
                # print("Data sent successfully.")
                break  # Success, exit retry loop
            except Exception as e:
                # print(f"Attempt {attempt + 1} failed: {e}")
                time.sleep(10)
        else:
            # All retries failed — reset the board
            # print("All attempts failed. Resetting...")
            microcontroller.reset()

    except Exception as outer_exception:
        # Sensor read or unexpected failure
        # print(f"Sensor or setup error: {outer_exception}")
        time.sleep(30)

    # Wait 15 minutes before next reading
    time.sleep(900)
