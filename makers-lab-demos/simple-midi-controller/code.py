'''
Three-button USB MIDI (Control Change) controller for Adafruit KB2040 / QT Py RP2040.

Behavior:
- Three debounced momentary pushbuttons (active-low with internal pull-up).
- On press: sends MIDI CC with value 127 and sets NeoPixel color:
    A0 -> CC64 -> Red
    A1 -> CC65 -> Green
    A2 -> CC66 -> Blue
- On release: sends MIDI CC with value 0 and updates NeoPixel based on currently pressed buttons.

Hardware:
- Each button goes between its pin (A0/A1/A2) and GND.
'''

import time
import board
import digitalio
import usb_midi

import neopixel
from adafruit_debouncer import Debouncer
import adafruit_midi
from adafruit_midi.control_change import ControlChange


# User settings
MIDI_CHANNEL = 1               # 1..16
CC_ON_VALUE = 127
CC_OFF_VALUE = 0

PIXEL_BRIGHTNESS = 0.2         # 0.0..1.0


# Button definitions: (pin, cc_number, color)
BUTTONS = [
    (board.A0, 64, (127, 0, 0)),   # Red
    (board.A1, 65, (0, 127, 0)),   # Green
    (board.A2, 66, (0, 0, 127)),   # Blue
]


# NeoPixel (single onboard)
pixel = neopixel.NeoPixel(board.NEOPIXEL, 1, brightness=PIXEL_BRIGHTNESS, auto_write=True)
pixel[0] = (0, 0, 0)


# USB MIDI out
midi = adafruit_midi.MIDI(midi_out=usb_midi.ports[1], out_channel=(MIDI_CHANNEL - 1))


def clamp7(v: int) -> int:
    return max(0, min(127, int(v)))


def send_cc(cc_number: int, value: int) -> None:
    midi.send(ControlChange(int(cc_number), clamp7(value)))


def set_pixel_from_pressed(pressed_mask) -> None:
    # pressed_mask is a list/tuple of booleans aligned with BUTTONS
    r = 0
    g = 0
    b = 0
    for i, is_pressed in enumerate(pressed_mask):
        if is_pressed:
            cr, cg, cb = BUTTONS[i][2]
            r = min(127, r + cr)
            g = min(127, g + cg)
            b = min(127, b + cb)
    pixel[0] = (r, g, b)


# Build debounced buttons
debounced = []
for pin, cc_num, color in BUTTONS:
    dio = digitalio.DigitalInOut(pin)
    dio.direction = digitalio.Direction.INPUT
    dio.pull = digitalio.Pull.UP
    debounced.append(Debouncer(dio))


# Initialize: LED off, send all CCs to OFF (optional but nice)
pixel[0] = (0, 0, 0)
for _, cc_num, _ in BUTTONS:
    send_cc(cc_num, CC_OFF_VALUE)

print("Starting 3-button USB MIDI CC controller")

while True:
    # Update all debouncers
    for b in debounced:
        b.update()

    # Handle edges
    for i, b in enumerate(debounced):
        pin, cc_num, color = BUTTONS[i]

        if b.fell:
            # pressed (active-low)
            send_cc(cc_num, CC_ON_VALUE)
            print("Pressed CC %d" % cc_num)

        if b.rose:
            # released
            # send_cc(cc_num, CC_OFF_VALUE)
            print("Released CC %d" % cc_num)

    # Update LED based on which are currently pressed
    pressed_now = [not b.value for b in debounced]  # value False means pressed
    set_pixel_from_pressed(pressed_now)

    time.sleep(0.001)
