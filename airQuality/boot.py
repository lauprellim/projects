# This file gets read on startup, and allows data to be written onto the pi's filesystem.

import board
import digitalio
import storage

# If the switch pin is connected to ground CircuitPython can write to the drive
# storage.remount("/", readonly=switch.value)

# True = board cannot write to itself
# False = board can write onto itself

storage.remount("/", readonly=False)
