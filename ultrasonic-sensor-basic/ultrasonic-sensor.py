"""
    This program measures distance in cm from an HC-SR04 sensor
    or compatible device (e.g., RCWL-1601). It formats the data
    such that it can be passed through the serial port to a
    patch in PureData (Pd).
    
    We are using Micropython here.
    
    Used as a template in the Duquesne Maker's Workshop.
"""

import machine
import utime

# Define GPIO pins for trigger and echo: check pinout
trigger_pin = 17
echo_pin = 16

# Configure the pins
trigger = machine.Pin(trigger_pin, machine.Pin.OUT)
echo = machine.Pin(echo_pin, machine.Pin.IN)

def measure_distance():
    # Send a 10us pulse to trigger the sensor
    trigger.low()
    utime.sleep_us(2)
    trigger.high()
    utime.sleep_us(10)
    trigger.low()

    # Measure the time it takes for the echo to return
    while echo.value() == 0:
        pulse_start = utime.ticks_us()
    while echo.value() == 1:
        pulse_end = utime.ticks_us()

    # Calculate the pulse duration and distance
    pulse_duration = pulse_end - pulse_start
    # Speed of sound is approximately 343.2 m/s or 0.0343 cm/us
    distance_cm = (pulse_duration * 0.0343) / 2  
    return distance_cm

while True:
    distance = measure_distance()
    # format for PureData patch using syntax similiar to C/C++
    print("%.2f" % distance)
    # delay 100ms or 0.1sec
    utime.sleep(0.1)