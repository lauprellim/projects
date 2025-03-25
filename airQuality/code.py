# read data from the air quality sensor and format it as a list
# for max/msp -- paul

import time
import board
import busio
import digitalio
import os
from adafruit_pm25.i2c import PM25_I2C

reset_pin = None
i2c = busio.I2C(board.GP21, board.GP20, frequency=100000)

# Connect to a PM2.5 sensor over I2C
pm25 = PM25_I2C(i2c, reset_pin)

# define a counter (fileNum) and a boolean
fileNum = 0
fileStatus = True

# the pico's onboard LED -- turn it on when board gets power
led = digitalio.DigitalInOut(board.LED)
led.direction = digitalio.Direction.OUTPUT
led.value = False

# an LED lights up when the board is writing to the filesystem
ledWrite = digitalio.DigitalInOut(board.GP15)
ledWrite.direction = digitalio.Direction.OUTPUT
ledWrite.value = False

# a switch to start logging air quality readings
switch = digitalio.DigitalInOut(board.GP16)
switch.direction = digitalio.Direction.INPUT
switch.pull = digitalio.Pull.UP

# a flag for the checking if the file is open or not
fileOpen = False

# the counter for placing the linecount at the beginning of each line
counter = 0

# this checks to see if the filename exists
def fileExists(fileName):
    try:
        os.stat(fileName)
        return True
    except OSError:
        return False

while True:
    # turn onboard LED on
    led.value = True

    # check to see if the fileName exists; iterate it; etc.
    while fileStatus:
        if fileExists(f"aq-{fileNum}.txt"):
            fileNum += 1
        else:
            fileName = f"aq-{fileNum}.txt"
            fileStatus = False

    # if the switch is OFF
    if switch.value:
        # and the file is open:
        if fileOpen:
            f.flush()
            f.close()
            fileOpen = False
            # reinitialize the line counter
            counter = 0
            time.sleep(1)

        # and the file is closed
        else:
            ledWrite.value = False
            time.sleep(1)
            fileStatus = True

    # the switch is ON
    else:
        # and the file is closed
        if not fileOpen:
            f = open(fileName, "a")
            fileOpen = True
            time.sleep(1)
        # and the switch is on
        else:
            try:
                aqdata = pm25.read()
                data01 = aqdata["particles 03um"]
                data02 = aqdata["particles 05um"]
                data03 = aqdata["particles 10um"]
                data04 = aqdata["particles 25um"]
                data05 = aqdata["particles 50um"]
                data06 = aqdata["particles 100um"]

                dataForMax = str(counter) + " " + str(data01) + " " + str(data02) + " " + str(data03) + " " + str(data04) + " " + str(data05) + " " + str(data06)

                f.write(dataForMax + "\n")
                counter+=1
                # print(dataForMax)
                ledWrite.value = True
            except RuntimeError:
                continue
            time.sleep(1)