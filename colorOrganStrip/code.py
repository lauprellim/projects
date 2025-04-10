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
numPixels = 90
pixels = neopixel.NeoPixel(board.A1,numPixels, brightness=0.5, auto_write=False)

pixelArray = [[0 for  x in range(3)] for y in range(numPixels)]

def movePixels(numPixels):
    for i in range(numPixels):
        pixelArray[numPixels-i-1][0] = pixelArray[numPixels-i-2][0]
        pixelArray[numPixels-i-1][1] = pixelArray[numPixels-i-2][1]
        pixelArray[numPixels-i-1][2] = pixelArray[numPixels-i-2][2]

while True:

    # read the secondary serial line by line when there's data
    # note that this assumes that the host always sends a full line
    if serial.in_waiting > 0:
        data_in = serial.readline()
        
        print(data_in)
        values = data_in.split()
        r = int(values[1])
        g = int(values[2])
        b = int(values[3])
        
        COLOR = (r, g, b)
        
        # move the second-to-last pixel to the last, and so on...
        movePixels(numPixels)
        # add the new value to the beginning of the strip
        pixelArray[0][0] = r
        pixelArray[0][1] = g
        pixelArray[0][2] = b
        
        print("-----")
        print(pixelArray)
        print("-----")
        
        for i in range(numPixels):
           pixels[i] = pixelArray[i]
        
        pixels.show()