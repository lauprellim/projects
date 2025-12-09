/*
  pico2_fft_spectrum_oled.ino

  Raspberry Pi Pico 2 + MAX9814 mic + 2.42" 128x64 OLED (SSD1305, SPI)
  Simple 16-band FFT spectrum analyzer:

    - Audio in: MAX9814 OUT -> GP28 (ADC2)
    - FFT: 256-point at 8 kHz using arduinoFFT (float)
    - Display: 16 vertical bars on OLED

  Required libraries:
    - arduinoFFT by Enrique Condes
    - Adafruit_GFX
    - Adafruit_SSD1305
*/

#include <Arduino.h>
#include <SPI.h>
#include <Adafruit_GFX.h>
#include <Adafruit_SSD1305.h>
#include <arduinoFFT.h>

// -------------------- OLED configuration --------------------

// Wiring (matches your working test sketch):
// OLED pin 1  (GND)  -> Pico GND
// OLED pin 2  (3.3V) -> Pico 3V3
// OLED pin 4  (DC)   -> Pico GP16
// OLED pin 7  (D0)   -> Pico GP18 (SCK)
// OLED pin 8  (D1)   -> Pico GP19 (MOSI)
// OLED pin 15 (CS)   -> Pico GP17
// OLED pin 16 (RST)  -> Pico GP20

#define OLED_MOSI   19    // GP19
#define OLED_CLK    18    // GP18
#define OLED_CS     17    // GP17
#define OLED_DC     16    // GP16
#define OLED_RESET  20    // GP20

#define SCREEN_WIDTH   128
#define SCREEN_HEIGHT  64

const uint32_t OLED_SPI_FREQ = 6000000UL;  // 6 MHz (safe for SSD1305)

// Hardware SPI constructor
Adafruit_SSD1305 display(SCREEN_WIDTH, SCREEN_HEIGHT, &SPI,
                         OLED_DC, OLED_RESET, OLED_CS, OLED_SPI_FREQ);

// -------------------- FFT configuration --------------------

const uint16_t SAMPLES            = 256;      // Must be power of 2
const double   SAMPLING_FREQUENCY = 8000.0;   // Hz
const uint8_t  NUM_BANDS          = 16;       // Number of bars

double vReal[SAMPLES];
double vImag[SAMPLES];

ArduinoFFT FFT(vReal, vImag, SAMPLES, SAMPLING_FREQUENCY);

// ADC pin for MAX9814 output (ADC2 / GP28)
const uint8_t MIC_PIN = 28;  // or A2, if your core defines that

// Sampling period in microseconds
const double samplingPeriodUS = 1000000.0 / SAMPLING_FREQUENCY;

// -------------------- Audio sampling --------------------
void sampleAudioFrame() {
  // Pico ADC is 12-bit (0..4095). DC offset from MAX9814 should be around mid-scale.
  const double dcOffset = 2048.0;

  for (uint16_t i = 0; i < SAMPLES; i++) {
    unsigned long tStart = micros();

    int raw = analogRead(MIC_PIN);          // 0 .. 4095
    double centered = (double)raw - dcOffset;

    // Store into FFT arrays
    vReal[i] = centered;
    vImag[i] = 0.0;

    // Wait until sampling period elapsed
    while (micros() - tStart < samplingPeriodUS) {
      // busy-wait
    }
  }
}

// -------------------- Compute band magnitudes --------------------
void computeBandMagnitudes(const double *fftMagnitudes, double *bands, uint8_t numBands) {
  const uint16_t binCount    = SAMPLES / 2;           // usable bins (0..Nyquist)
  const uint16_t binsPerBand = binCount / numBands;   // approx 8 for 256/2/16

  // Clear bands
  for (uint8_t b = 0; b < numBands; b++) {
    bands[b] = 0.0;
  }

  uint8_t  bandIndex = 0;
  uint16_t binInBand = 0;

  // Skip DC bin (k=0). Start from k=1.
  for (uint16_t k = 1; k < binCount; k++) {
    double mag = fftMagnitudes[k];

    bands[bandIndex] += mag;
    binInBand++;

    if (binInBand >= binsPerBand && bandIndex < numBands - 1) {
      bands[bandIndex] /= (double)binInBand;  // average
      bandIndex++;
      binInBand = 0;
    }
  }

  // Average last band if needed
  if (binInBand > 0 && bandIndex < numBands) {
    bands[bandIndex] /= (double)binInBand;
  }
}

// -------------------- Draw spectrum on OLED --------------------
void drawSpectrum(double *bands, uint8_t numBands) {
  display.clearDisplay();

  // change band[0] here if needed
  // band[0] *= 0.1;
  
  // Find max magnitude for normalization
  double maxMag = 1.0;
  for (uint8_t b = 0; b < numBands; b++) {
    if (bands[b] > maxMag) {
      maxMag = bands[b];
    }
  }
  if (maxMag < 1.0) {
    maxMag = 1.0;
  }

  const uint8_t barWidth  = SCREEN_WIDTH / numBands;    // e.g., 8 for 16 bands
  const uint8_t maxHeight = SCREEN_HEIGHT - 1;          // 0..63

  for (uint8_t b = 0; b < numBands; b++) {
    // Basic linear scaling; later you can swap in log scaling if you like.
    double norm = bands[b] / maxMag;
    if (norm > 1.0) norm = 1.0;

    uint8_t barHeight = (uint8_t)(norm * (double)maxHeight);

    uint8_t x = b * barWidth;
    uint8_t y = SCREEN_HEIGHT - barHeight;

    uint8_t effectiveWidth = (barWidth > 1) ? barWidth - 1 : barWidth;

    display.fillRect(x, y, effectiveWidth, barHeight, WHITE);
  }

  display.display();
}

// -------------------- Arduino setup & loop --------------------
void setup() {
  Serial.begin(115200);
  delay(300);
  Serial.println("Pico 2 FFT Spectrum Analyzer starting...");

  // ADC config
  analogReadResolution(12);
  analogRead(MIC_PIN);   // throw away first reading

  // OLED & SPI init
  SPI.setSCK(OLED_CLK);
  SPI.setTX(OLED_MOSI);
  SPI.begin();

  if (!display.begin(0x3C)) {  // address ignored for SPI but required by lib
    Serial.println("SSD1305 init failed");
    while (true) {
      delay(500);
    }
  }

  display.clearDisplay();
  display.setTextSize(1);
  display.setTextColor(WHITE);
  display.setCursor(0, 0);
  display.println("Pico 2 FFT Spectrum");
  display.println("Mic on GP28 (ADC2)");
  display.display();
  delay(1000);
}

void loop() {
  static double bands[NUM_BANDS];

  // 1. Acquire samples
  sampleAudioFrame();

  // 2. FFT
  FFT.windowing(FFT_WIN_TYP_HAMMING, FFT_FORWARD);  // window in-place
  FFT.compute(FFT_FORWARD);
  FFT.complexToMagnitude();                         // magnitudes in vReal[]

  // 3. Bin into 16 bands
  computeBandMagnitudes(vReal, bands, NUM_BANDS);

  // 4. Draw on OLED
  drawSpectrum(bands, NUM_BANDS);

  // Optional: small delay to keep overall FPS reasonable
  // (most of time is in sampleAudioFrame + FFT anyway)
  // delay(10);
}
