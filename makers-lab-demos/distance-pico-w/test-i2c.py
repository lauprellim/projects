from machine import Pin, I2C
import time

# Common Pico I2C0 pins: SDA=0, SCL=1
i2c = I2C(0, sda=Pin(0), scl=Pin(1), freq=400000)

time.sleep(0.2)
print("I2C devices:", [hex(x) for x in i2c.scan()])