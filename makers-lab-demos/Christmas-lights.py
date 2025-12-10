"""
Raspberry Pi Pico + NeoPixel Pebble Strand (200 LEDs)

Button cycles through 4 modes:

  Mode 1: Dim, colorful background + white sparkles
          - Each LED has a dim, saturated base color
          - Occasionally a LED brightens to near-white, then returns to its base color

  Mode 2: Alternating white, red, and green
          - Pattern along strip: white, red, green, white, red, green, ...
          - ALL LEDs (white, red, green) can sparkle (brighten toward white, then back)

  Mode 3: Twinkling snow
          - All LEDs very dim white
          - Individual LEDs slowly brighten to soft white and fade back down
          - Gentle, random twinkles across the strand

  Mode 4: Off
          - All LEDs off (black)
"""

from machine import Pin
from neopixel import NeoPixel
import time
import urandom
import math

# ----------------- CONFIGURATION -----------------

LED_PIN = 2          # GPIO for NeoPixel data
NUM_LEDS = 200       # Pebble strand length
BUTTON_PIN = 15      # GPIO for button (to GND, internal pull-up)

FPS = 40             # Target animation frame rate
FRAME_DELAY = int(1000 / FPS)

# Mode 1: base glow + sparkles
MODE1_BASE_V = 0.06          # background dim level
MODE1_SPARKLE_V = 0.95       # peak brightness during sparkle (near white)
MODE1_SPARKLE_STEPS = 22     # length of sparkle animation in frames
MODE1_SPARKLE_PROB = 40      # 0–255 chance per frame to start a sparkle

# Mode 2: explicit white / red / green + sparkles on all LEDs
# Your strip appears to be GBR-ordered:
#   tuple[0] -> GREEN, tuple[1] -> BLUE, tuple[2] -> RED
MODE2_WHITE_VAL    = 40      # base white brightness (0–255)
MODE2_RED_VAL      = 25      # base RED brightness (0–255)  -> channel 2
MODE2_GREEN_VAL    = 25      # base GREEN brightness (0–255)-> channel 0
MODE2_SPARKLE_VAL  = 220     # how bright white sparkles go (0–255)

# Mode 3: twinkling snow
MODE3_BASE_V = 0.01          # background very dim white
MODE3_TWINKLE_V = 0.5       # peak brightness of a snow twinkle (still gentle)
MODE3_TWINKLE_STEPS = 60     # how many frames a twinkle lasts (~1.5 s at 40 FPS)
MODE3_TWINKLE_PROB = 210      # 0–255 chance per frame to start a new twinkle

# Button debouncing
BUTTON_DEBOUNCE_MS = 250

# ----------------- HARDWARE SETUP -----------------

pin = Pin(LED_PIN, Pin.OUT)
np = NeoPixel(pin, NUM_LEDS)

button = Pin(BUTTON_PIN, Pin.IN, Pin.PULL_UP)  # active low

# ----------------- STATE VARIABLES -----------------

current_mode = 1
last_button_time = 0

# Mode 1 state
base_hue_mode1 = [0.0] * NUM_LEDS
sparkle_phase = [0] * NUM_LEDS   # 0 = no sparkle, >0 = which step in sparkle

# Mode 2 state
sparkle_phase2 = [0] * NUM_LEDS  # used for white/red/green pixels

# Mode 3 state
twinkle_phase3 = [0] * NUM_LEDS  # 0 = no twinkle, >0 = step in twinkle

# ----------------- HELPER FUNCTIONS -----------------

def hsv_to_rgb(h, s, v):
    """
    h, s, v in [0,1] -> (r,g,b) in [0,255]
    (Logical RGB; for Mode 2 primaries we override with GBR mapping.)
    """
    if s <= 0.0:
        val = int(v * 255)
        return val, val, val

    h = h % 1.0  # wrap around
    i = int(h * 6.0)
    f = (h * 6.0) - i
    p = v * (1.0 - s)
    q = v * (1.0 - s * f)
    t = v * (1.0 - s * (1.0 - f))
    i = i % 6

    if i == 0:
        r, g, b = v, t, p
    elif i == 1:
        r, g, b = q, v, p
    elif i == 2:
        r, g, b = p, v, t
    elif i == 3:
        r, g, b = p, q, v
    elif i == 4:
        r, g, b = t, p, v
    else:  # i == 5
        r, g, b = v, p, q

    return int(r * 255), int(g * 255), int(b * 255)


def random_float():
    # Quick 0.0–1.0 random using urandom
    return urandom.getrandbits(16) / 65535.0


def lerp(a, b, t):
    """Linear interpolation between a and b with t in [0,1]."""
    return int(a + (b - a) * t)

# ----------------- MODE INITIALISATION -----------------

def init_mode1():
    """
    Mode 1: each LED gets a dim, saturated base color.
    Sparkles will temporarily send LEDs toward bright white.
    """
    global base_hue_mode1, sparkle_phase
    for i in range(NUM_LEDS):
        base_hue_mode1[i] = random_float()
        sparkle_phase[i] = 0

    for i in range(NUM_LEDS):
        r, g, b = hsv_to_rgb(base_hue_mode1[i], 1.0, MODE1_BASE_V)
        np[i] = (r, g, b)
    np.write()


def init_mode2():
    """
    Mode 2:
    - Static spatial pattern of white, red, green repeated.
    - ALL LEDs (white, red, green) may sparkle.
    """
    global sparkle_phase2

    for i in range(NUM_LEDS):
        pattern = i % 3  # 0: white, 1: red, 2: green

        if pattern == 0:
            # White: all three channels equal -> white regardless of order
            np[i] = (MODE2_WHITE_VAL, MODE2_WHITE_VAL, MODE2_WHITE_VAL)
        elif pattern == 1:
            # RED on GBR hardware: channel 2 is red
            np[i] = (0, 0, MODE2_RED_VAL)        # (G, B, R)
        else:
            # GREEN on GBR hardware: channel 0 is green
            np[i] = (MODE2_GREEN_VAL, 0, 0)      # (G, B, R)

        sparkle_phase2[i] = 0

    np.write()


def init_mode3():
    """
    Mode 3: Twinkling snow.
    - All LEDs start at very dim white.
    - twinkle_phase3 is reset so no LEDs are currently twinkling.
    """
    global twinkle_phase3
    for i in range(NUM_LEDS):
        twinkle_phase3[i] = 0

    base_val = int(MODE3_BASE_V * 255)
    for i in range(NUM_LEDS):
        np[i] = (base_val, base_val, base_val)
    np.write()


def init_mode4():
    """
    Mode 4: Off (all LEDs black).
    """
    for i in range(NUM_LEDS):
        np[i] = (0, 0, 0)
    np.write()

# ----------------- MODE UPDATE FUNCTIONS -----------------

def update_mode1():
    """
    Mode 1:
    - Dim colorful background.
    - Sparkles: LED brightens toward near-white, then returns to its original color.
    """
    # Possibly start a new sparkle
    if urandom.getrandbits(8) < MODE1_SPARKLE_PROB:
        idx = urandom.getrandbits(16) % NUM_LEDS
        if sparkle_phase[idx] == 0:
            sparkle_phase[idx] = 1

    half = MODE1_SPARKLE_STEPS // 2

    for i in range(NUM_LEDS):
        phase = sparkle_phase[i]

        if phase == 0:
            # No sparkle, just base color
            s = 1.0
            v = MODE1_BASE_V
        else:
            # Envelope for whiteness/brightness: 0 → 1 → 0
            if phase <= half:
                u = phase / half
            else:
                u = (MODE1_SPARKLE_STEPS - phase) / half

            u = max(0.0, min(1.0, u))
            u = u ** 1.5  # slightly sharper

            # u controls how "white and bright" we are:
            # u = 0: fully saturated base color at MODE1_BASE_V
            # u = 1: desaturated (white) at MODE1_SPARKLE_V
            s = 1.0 - u
            v = MODE1_BASE_V + (MODE1_SPARKLE_V - MODE1_BASE_V) * u

            sparkle_phase[i] += 1
            if sparkle_phase[i] > MODE1_SPARKLE_STEPS:
                sparkle_phase[i] = 0
                s = 1.0
                v = MODE1_BASE_V

        r, g, b = hsv_to_rgb(base_hue_mode1[i], s, v)
        np[i] = (r, g, b)

    np.write()


def update_mode2():
    """
    Mode 2:
    - White, red, green pattern along the strip.
    - ALL LEDs (white, red, green) can sparkle:
        * randomly chosen
        * brighten toward white, then fade back to their base color.
    """
    global sparkle_phase2

    # Possibly start a new sparkle on ANY LED (white, red, or green)
    if urandom.getrandbits(8) < MODE1_SPARKLE_PROB:
        idx = urandom.getrandbits(16) % NUM_LEDS
        if sparkle_phase2[idx] == 0:
            sparkle_phase2[idx] = 1

    half = MODE1_SPARKLE_STEPS // 2

    for i in range(NUM_LEDS):
        pattern = i % 3  # 0: white, 1: red, 2: green
        phase = sparkle_phase2[i]

        # Base color in (G, B, R) tuple order
        if pattern == 0:
            # white
            base_g = MODE2_WHITE_VAL
            base_b = MODE2_WHITE_VAL
            base_r = MODE2_WHITE_VAL
        elif pattern == 1:
            # red
            base_g, base_b, base_r = 0, 0, MODE2_RED_VAL
        else:
            # green
            base_g, base_b, base_r = MODE2_GREEN_VAL, 0, 0

        if phase == 0:
            # No sparkle, just base color
            g, b, r = base_g, base_b, base_r
        else:
            # Same sparkle envelope shape as Mode 1: 0 → 1 → 0
            if phase <= half:
                u = phase / half
            else:
                u = (MODE1_SPARKLE_STEPS - phase) / half

            u = max(0.0, min(1.0, u))
            u = u ** 1.5

            # Blend from base color → white at MODE2_SPARKLE_VAL
            g = lerp(base_g, MODE2_SPARKLE_VAL, u)
            b = lerp(base_b, MODE2_SPARKLE_VAL, u)
            r = lerp(base_r, MODE2_SPARKLE_VAL, u)

            sparkle_phase2[i] += 1
            if sparkle_phase2[i] > MODE1_SPARKLE_STEPS:
                sparkle_phase2[i] = 0
                g, b, r = base_g, base_b, base_r

        # Remember: (G, B, R) for your strip
        np[i] = (g, b, r)

    np.write()


def update_mode3():
    """
    Mode 3: Twinkling snow.
    - Background is very dim white.
    - Individual LEDs fade up to soft white and back down, randomly across the strand.
    """
    global twinkle_phase3

    # Possibly start a new twinkle on a random LED
    if urandom.getrandbits(8) < MODE3_TWINKLE_PROB:
        idx = urandom.getrandbits(16) % NUM_LEDS
        if twinkle_phase3[idx] == 0:
            twinkle_phase3[idx] = 1

    half = MODE3_TWINKLE_STEPS // 2

    for i in range(NUM_LEDS):
        phase = twinkle_phase3[i]

        if phase == 0:
            v = MODE3_BASE_V
        else:
            # Soft symmetric envelope: 0 → 1 → 0 over MODE3_TWINKLE_STEPS
            if phase <= half:
                u = phase / half
            else:
                u = (MODE3_TWINKLE_STEPS - phase) / half

            u = max(0.0, min(1.0, u))
            u = u ** 1.3  # gentle shaping

            v = MODE3_BASE_V + (MODE3_TWINKLE_V - MODE3_BASE_V) * u

            twinkle_phase3[i] += 1
            if twinkle_phase3[i] > MODE3_TWINKLE_STEPS:
                twinkle_phase3[i] = 0
                v = MODE3_BASE_V

        val = int(v * 255)
        # Equal channels => white, independent of GBR quirk
        np[i] = (val, val, val)

    np.write()


def update_mode4():
    """
    Mode 4: Off (all LEDs black).
    We still rewrite every frame to be robust if anything else touched the strip.
    """
    for i in range(NUM_LEDS):
        np[i] = (0, 0, 0)
    np.write()

# ----------------- BUTTON / MODE HANDLING -----------------

def check_button():
    """
    Simple debounced button check.
    Button is active low (0 when pressed).
    Cycles through modes 1 → 2 → 3 → 4 → 1 → ...
    """
    global current_mode, last_button_time

    now = time.ticks_ms()
    if button.value() == 0:  # pressed
        if time.ticks_diff(now, last_button_time) > BUTTON_DEBOUNCE_MS:
            if current_mode == 1:
                current_mode = 2
                init_mode2()
            elif current_mode == 2:
                current_mode = 3
                init_mode3()
            elif current_mode == 3:
                current_mode = 4
                init_mode4()
            else:
                current_mode = 1
                init_mode1()

            last_button_time = now

# ----------------- MAIN LOOP -----------------

def main():
    global current_mode

    # Start in mode 1 by default
    init_mode1()

    while True:
        start = time.ticks_ms()
        check_button()

        if current_mode == 1:
            update_mode1()
        elif current_mode == 2:
            update_mode2()
        elif current_mode == 3:
            update_mode3()
        else:
            update_mode4()

        # Try to keep roughly constant frame time
        elapsed = time.ticks_diff(time.ticks_ms(), start)
        delay = FRAME_DELAY - elapsed
        if delay > 0:
            time.sleep_ms(delay)

main()

