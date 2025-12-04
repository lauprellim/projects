"""
Sound-reactive NeoPixel ring (24 LEDs) using Raspberry Pi Pico (RP2040) + MAX9814 mic.

Behavior:
- All 24 LEDs are always on.
- At quiet levels, the ring is very dim and pale (almost white).
- As the audio level increases:
    * LEDs get brighter.
    * Colors become more saturated.
    * The overall hue shifts around the color wheel with loudness.

Wiring:
  MAX9814:
    VDD  -> 3V3 on Pico
    GND  -> GND on Pico
    OUT  -> GP28 / ADC2 on Pico

  NeoPixel ring (24 LEDs):
    DIN  -> GP2 on Pico (through ~330 ohm resistor, if possible)
    V+   -> 5V supply (or ~4–5 V from USB / separate supply)
    GND  -> GND (same as Pico ground)

Make sure the 'neopixel' module is available in MicroPython.
"""

import machine
import neopixel
import time
import math

# ----------- Configuration -----------

MIC_ADC_PIN = 28          # GP28 = ADC2
PIXEL_PIN = 2             # GP2 for NeoPixel data
NUM_PIXELS = 24           # 24-LED ring

SAMPLE_COUNT = 100        # samples per loudness estimate
UPDATE_DELAY = 0.03       # seconds between LED updates

# Exponential smoothing (0 = no smoothing, 1 = very slow)
LEVEL_SMOOTHING = 0.6

# Loudness scaling (tune for your environment)
NOISE_FLOOR = 500.0       # below this, treat as silence
MAX_LEVEL = 6000.0        # approximate "very loud" level

# Brightness bounds (0..1 scale applied to each RGB channel)
MIN_BRIGHTNESS = 0.05     # quiet level brightness
MAX_BRIGHTNESS = 0.40     # loud level brightness


# ----------- Setup hardware -----------

adc = machine.ADC(MIC_ADC_PIN)
pixels = neopixel.NeoPixel(machine.Pin(PIXEL_PIN), NUM_PIXELS)

# Estimate DC offset (bias) at startup
print("Measuring DC offset...")
offset_sum = 0
N_OFFSET = 2000
for _ in range(N_OFFSET):
    offset_sum += adc.read_u16()
dc_offset = offset_sum / N_OFFSET
print("Estimated DC offset:", dc_offset)


# ----------- Helper functions -----------

def wheel(pos):
    """
    Standard NeoPixel color wheel.
    Input: 0-255
    Output: (r, g, b) saturated color.
    """
    if pos < 0 or pos > 255:
        return (0, 0, 0)
    if pos < 85:
        return (255 - pos * 3, pos * 3, 0)
    if pos < 170:
        pos -= 85
        return (0, 255 - pos * 3, pos * 3)
    pos -= 170
    return (pos * 3, 0, 255 - pos * 3)


def measure_loudness():
    """
    Take SAMPLE_COUNT ADC readings, remove DC offset, and compute
    an RMS-based loudness measure.
    """
    sum_sq = 0.0
    for _ in range(SAMPLE_COUNT):
        raw = adc.read_u16()
        centered = raw - dc_offset
        sum_sq += centered * centered

    rms = math.sqrt(sum_sq / SAMPLE_COUNT)

    # Suppress noise floor
    if rms < NOISE_FLOOR:
        rms = 0.0

    return rms


# ----------- Main loop -----------

print("Starting sound-reactive pastel halo...")
smoothed_level = 0.0

while True:
    # Measure raw loudness (RMS units)
    rms = measure_loudness()

    # Normalize to 0..1
    level = rms / MAX_LEVEL
    if level > 1.0:
        level = 1.0

    # Smooth the level over time
    smoothed_level = (
        LEVEL_SMOOTHING * smoothed_level
        + (1.0 - LEVEL_SMOOTHING) * level
    )

    # Map smoothed_level to brightness (0..1)
    brightness = (
        MIN_BRIGHTNESS
        + (MAX_BRIGHTNESS - MIN_BRIGHTNESS) * smoothed_level
    )

    # Desaturation amount:
    # quiet  -> desat_amount ~ 1.0  (mostly white)
    # loud   -> desat_amount ~ 0.0  (full saturated color)
    desat_amount = 1.0 - smoothed_level

    # Very dim white base at quiet levels
    white_base = 20  # was 180; now extremely faint

    # Base hue shifts with loudness:
    # quiet  -> base_hue near 0
    # loud   -> base_hue near 255
    base_hue = int(smoothed_level * 255) & 0xFF

    for i in range(NUM_PIXELS):
        # Spread a rainbow around the ring, offset by base_hue
        hue_pos = (base_hue + (i * 256) // NUM_PIXELS) & 0xFF
        r_sat, g_sat, b_sat = wheel(hue_pos)

        # Mix saturated color with white (desaturation)
        r = int(r_sat * (1.0 - desat_amount) + white_base * desat_amount)
        g = int(g_sat * (1.0 - desat_amount) + white_base * desat_amount)
        b = int(b_sat * (1.0 - desat_amount) + white_base * desat_amount)

        # Apply overall brightness scaling
        r = int(r * brightness)
        g = int(g * brightness)
        b = int(b * brightness)

        pixels[i] = (r, g, b)

    pixels.write()
    time.sleep(UPDATE_DELAY)
