"""
This needs to go in boot.py on the Raspberry Pi Pico:

import usb_cdc
usb_cdc.enable(console=True, data=True)

This repo can be useful:
https://github.com/Neradoc/circuitpython-sample-scripts/blob/main/usb_serial/README.md

"""

import board
import time
import usb_cdc
import neopixel

serial = usb_cdc.data
numPixels = 16
pixels = neopixel.NeoPixel(board.A1,numPixels, brightness=0.5, auto_write=False)

while True:

    # read the secondary serial line by line when there's data
    # note that this assumes that the host always sends a full line
    if serial.in_waiting > 0:
        data_in = serial.readline()
        
        print(data_in)
        values = data_in.split()
        address = int(values[0])
        r = int(values[1])
        g = int(values[2])
        b = int(values[3])
        
        # print(str(values))

        COLOR = (r, g, b)
        pixels[address] = COLOR
        pixels.show()

   
