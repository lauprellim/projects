# Written by Paul V. Miller
# Media Maker's Lab 2025-26 Project
#
# Raspberry Pi Pico W + SHT45 temperature/humidity sensor
#
# This program reads temperature/humidity data from an SHT45 sensor
# and sends the data to a server-side script every 15 minutes.
#
# Device-specific settings are stored in settings.toml.

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


# -------------------------
# Settings from settings.toml
# -------------------------

WIFI_SSID = os.getenv("CIRCUITPY_WIFI_SSID")
WIFI_PASSWORD = os.getenv("CIRCUITPY_WIFI_PASSWORD")

ID_LOCATIONS = int(os.getenv("ID_LOCATIONS"))
API_TOKEN = os.getenv("API_TOKEN")

DEBUG = os.getenv("DEBUG") == "1"


# -------------------------
# Program configuration
# -------------------------

SEND_INTERVAL_SECONDS = 900       # 15 minutes
RETRY_DELAY_SECONDS = 20
MAX_SEND_ATTEMPTS = 3
MAX_FAILURE_CYCLES = 8

# This HTTPS URL is the most likely place where SSL/certificate problems may occur.
# If the Pico W cannot validate the certificate, the request may fail here.
BASE_URL = "https://www.theoryofpaul.net/private/environment/environment-duq/enter-data.phtml?"


# -------------------------
# Helper functions
# -------------------------

def debug(message):
    """Print debugging messages only when DEBUG is enabled."""
    if DEBUG:
        print(message)


def connect_wifi():
    """Connect or reconnect to WiFi."""

    if wifi.radio.connected:
        return

    debug("Connecting to WiFi...")

    if WIFI_PASSWORD:
        wifi.radio.connect(WIFI_SSID, WIFI_PASSWORD)
    else:
        wifi.radio.connect(WIFI_SSID)

    debug("Connected to WiFi.")
    debug("IP address: %s" % wifi.radio.ipv4_address)


def make_requests_session():
    """Create a fresh HTTPS-capable requests session."""

    pool = socketpool.SocketPool(wifi.radio)
    ssl_context = ssl.create_default_context()

    return adafruit_requests.Session(pool, ssl_context)


def send_reading(requests, temp, hum):
    """Send one temperature/humidity reading to the server."""

    url_temp = "%3.1f" % temp
    url_hum = "%3.1f" % hum

    formatted_url = (
        BASE_URL
        + "temp=%s&humidity=%s&idLocations=%d&apiToken=%s"
        % (url_temp, url_hum, ID_LOCATIONS, API_TOKEN)
    )

    debug("Sending data: temp=%s C, humidity=%s %%" % (url_temp, url_hum))

    response = None

    try:
        response = requests.get(formatted_url)
        debug("Server status: %d" % response.status_code)

        return response.status_code == 200

    finally:
        if response is not None:
            response.close()


def sleep_with_status(seconds):
    """Sleep quietly, but leave a debug hook for development."""

    debug("Sleeping for %d seconds." % seconds)
    time.sleep(seconds)


# -------------------------
# Initialize sensor
# -------------------------

debug("Initializing SHT45 sensor...")

i2c = busio.I2C(scl=board.GP1, sda=board.GP0)

sht = adafruit_sht4x.SHT4x(i2c)
sht.mode = adafruit_sht4x.Mode.NOHEAT_HIGHPRECISION

time.sleep(1)

debug("Sensor initialized.")


# -------------------------
# Initialize network
# -------------------------

connect_wifi()
requests = make_requests_session()


# -------------------------
# Main loop
# -------------------------

failure_cycles = 0

while True:

    success = False

    try:
        temp, hum = sht.measurements

        for attempt in range(1, MAX_SEND_ATTEMPTS + 1):

            try:
                debug("Send attempt %d of %d" % (attempt, MAX_SEND_ATTEMPTS))

                connect_wifi()

                success = send_reading(requests, temp, hum)

                if success:
                    failure_cycles = 0
                    debug("Data sent successfully.")
                    break

                debug("Server did not return HTTP 200.")

            except Exception as e:
                debug("Send attempt failed: %s" % repr(e))

                try:
                    requests = make_requests_session()
                except Exception as session_error:
                    debug("Could not rebuild requests session: %s" % repr(session_error))

                time.sleep(RETRY_DELAY_SECONDS)

        if not success:
            failure_cycles += 1
            debug("Failure cycle count: %d" % failure_cycles)

            if failure_cycles >= MAX_FAILURE_CYCLES:
                microcontroller.reset()

    except Exception as e:
        failure_cycles += 1
        debug("Main loop error: %s" % repr(e))
        debug("Failure cycle count: %d" % failure_cycles)

        if failure_cycles >= MAX_FAILURE_CYCLES:
            microcontroller.reset()

    sleep_with_status(SEND_INTERVAL_SECONDS)
