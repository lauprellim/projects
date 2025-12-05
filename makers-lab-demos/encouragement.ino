#include <Wire.h>
#include <Adafruit_GFX.h>
#include <Adafruit_SSD1306.h>

#define SCREEN_WIDTH 128
#define SCREEN_HEIGHT 32

Adafruit_SSD1306 display(SCREEN_WIDTH, SCREEN_HEIGHT, &Wire, -1);

#define OLED_I2C_ADDRESS 0x3C

// Button on D5, wired: D5 ---- button ---- GND
const int BUTTON_PIN = 5;

// Debounce variables
bool buttonState       = HIGH;
bool lastButtonReading = HIGH;
unsigned long lastDebounceTime = 0;
const unsigned long debounceDelay = 50;

// Message display timing
bool messageShowing = false;
unsigned long messageStartTime = 0;
const unsigned long messageDuration = 5000; // 5 seconds

// Messages (customize freely)
const char* messages[] = {
  "Mom and dad\nlove you lots.",
  "You are great\nat basketball!",
  "You have lots of\nfriends at school.",
  "Santa will bring\nmany surprises.",
  "Vegetables are\nbetter than\nyou might think!",
  "You can't do as badly\nas the Steelers.",
  "It is fun to\nplay with you!",
  "You're terrific\nat drums!",
  "We think you\nare great at art!"
};

const size_t NUM_MESSAGES = sizeof(messages) / sizeof(messages[0]);
size_t currentIndex = 0;  // <— NEW: keeps track of which message is next

void showMessage(const char* msg) {
  display.clearDisplay();
  display.setTextSize(1);
  display.setTextColor(SSD1306_WHITE);
  display.setCursor(0, 0);
  display.println(msg);
  display.display();
}

void clearScreen() {
  display.clearDisplay();
  display.display();
}

void setup() {
  Serial.begin(115200);
  pinMode(BUTTON_PIN, INPUT_PULLUP);

  if (!display.begin(SSD1306_SWITCHCAPVCC, OLED_I2C_ADDRESS)) {
    while (true);
  }

  clearScreen(); // Start blank
}

void loop() {
  // ----- Debounce -----
  bool rawReading = digitalRead(BUTTON_PIN);

  if (rawReading != lastButtonReading) {
    lastDebounceTime = millis();
    lastButtonReading = rawReading;
  }

  if ((millis() - lastDebounceTime) > debounceDelay) {
    if (rawReading != buttonState) {
      buttonState = rawReading;

      if (buttonState == LOW) { // pressed
        if (!messageShowing) {
          // Show the next message in order
          showMessage(messages[currentIndex]);

          // Advance index for next press
          currentIndex++;
          if (currentIndex >= NUM_MESSAGES) {
            currentIndex = 0; // wrap around
          }

          messageShowing = true;
          messageStartTime = millis();
        }
      }
    }
  }

  // ----- Auto-clear after 5 seconds -----
  if (messageShowing) {
    if (millis() - messageStartTime >= messageDuration) {
      clearScreen();
      messageShowing = false;
    }
  }

  delay(5);
}
