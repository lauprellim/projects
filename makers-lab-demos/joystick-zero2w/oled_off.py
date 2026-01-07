#!/usr/bin/python3
'''
oled_off.py
Clear and (if supported) power off an SSD1306 OLED on I2C during shutdown.
Assumes 128x32 at I2C address 0x3C.
This goes in /usr/local/bin/oled_off.py
'''

import time
import board
import busio
import adafruit_ssd1306

def main():
    i2c = busio.I2C(board.SCL, board.SDA)
    oled = adafruit_ssd1306.SSD1306_I2C(128, 32, i2c, addr=0x3C)

    # Clear framebuffer
    oled.fill(0)
    oled.show()
    time.sleep(0.05)

    # Power off if the library supports it
    try:
        oled.poweroff()
    except Exception:
        pass

if __name__ == "__main__":
    main()
