/*
  fft-display.ino

  Raspberry Pi Pico 2 + MAX9814 mic + 2.42" 128x64 SSD1305 OLED (SPI)

  Features:
    - 256-point FFT at 8 kHz (31.25 Hz bin spacing)
    - 128 display bands (bar graph)
    - Quiet-room behavior:
        * noise gate (graph goes calm when quiet)
        * slow normalization reference (scale does not chase noise)
    - Pitch display:
        * dominant bin search with parabolic peak interpolation
        * confidence gating (peak magnitude + peak-to-average ratio)
        * frequency smoothing
        * note hysteresis (candidate must persist N frames)
        * A4 = 440 Hz, equal temperament, sharps preferred (F# not Gb)
    - Lowest display band suppressed (bands[0]=0)

  Wiring:
    MAX9814 OUT -> Pico GP28 (ADC2)

    OLED (Adafruit SSD1305 2.42" 128x64, SPI mode):
      Pin 1  GND   -> Pico GND
      Pin 2  3.3V  -> Pico 3V3
      Pin 4  DC    -> Pico GP16
      Pin 7  D0    -> Pico GP18 (SPI0 SCK)
      Pin 8  D1    -> Pico GP19 (SPI0 MOSI)
      Pin 15 CS    -> Pico GP17
      Pin 16 RST   -> Pico GP20
*/

#include <Arduino.h>
#include <SPI.h>
#include <math.h>
#include <Adafruit_GFX.h>
#include <Adafruit_SSD1305.h>
#include <arduinoFFT.h>

/* -------------------- OLED configuration -------------------- */

#define OLED_MOSI   19    /* GP19 */
#define OLED_CLK    18    /* GP18 */
#define OLED_CS     17    /* GP17 */
#define OLED_DC     16    /* GP16 */
#define OLED_RESET  20    /* GP20 */

#define SCREEN_WIDTH   128
#define SCREEN_HEIGHT  64

const uint32_t OLED_SPI_FREQ = 6000000UL;

Adafruit_SSD1305 display(SCREEN_WIDTH, SCREEN_HEIGHT, &SPI,
                         OLED_DC, OLED_RESET, OLED_CS, OLED_SPI_FREQ);

/* -------------------- FFT configuration -------------------- */

const uint16_t SAMPLES            = 256;      /* FFT length (N) */
const double   SAMPLING_FREQUENCY = 8000.0;   /* Fs in Hz */
const uint8_t  NUM_BANDS          = 128;       /* display bands */

double vReal[SAMPLES];
double vImag[SAMPLES];

ArduinoFFT FFT = ArduinoFFT(vReal, vImag, SAMPLES, SAMPLING_FREQUENCY);

/* Mic pin: ADC2 / GP28 */
const uint8_t MIC_PIN = 28;

/* Sampling period in microseconds (125 us for 8 kHz) */
const double samplingPeriodUS = 1000000.0 / SAMPLING_FREQUENCY;

/* -------------------- Display behavior tuning -------------------- */

/* A slow reference so the bar scaling does not chase noise */
double maxRef = 1.0;
/* Closer to 1.0 = slower decay (more stable). */
const double MAXREF_DECAY = 0.992;

/*
  Noise gate threshold for the bar graph.
  This is based on average band magnitude (bands 1..15).
  You will likely want to tune this slightly for your mic/gain.
*/
const double QUIET_THRESHOLD = 80.0;

/* -------------------- Pitch detection tuning -------------------- */

/*
  Confidence gating. A detected peak must be:
    - above PEAK_MAG_THRESHOLD
    - and PEAK_RATIO_THRESHOLD times larger than average magnitude
*/
const double PEAK_MAG_THRESHOLD   = 300.0;
const double PEAK_RATIO_THRESHOLD = 6.0;

/* Frequency smoothing: smaller alpha = more lag. */
const double FREQ_SMOOTH_ALPHA = 0.15;

/* Note hysteresis: candidate note must persist N frames to switch. */
const uint8_t NOTE_STABLE_FRAMES = 5;

/* If we lose confidence, keep the last displayed note for a short time. */
const uint8_t NOTE_HOLD_FRAMES = 10;

/* State for pitch smoothing and hysteresis */
double smoothedFreqHz = 0.0;
int currentMidi = -1;
int candidateMidi = -1;
uint8_t candidateCount = 0;
uint8_t noteHoldCount = 0;

/* -------------------- Utility: sampling -------------------- */

void sampleAudioFrame() {
  const double dcOffset = 2048.0; /* mid-scale for 12-bit ADC */

  for (uint16_t i = 0; i < SAMPLES; i++) {
    unsigned long tStart = micros();

    int raw = analogRead(MIC_PIN);     /* 0..4095 */
    double centered = (double)raw - dcOffset;

    vReal[i] = centered;
    vImag[i] = 0.0;

    while ((double)(micros() - tStart) < samplingPeriodUS) {
      /* busy wait to approximate constant Fs */
    }
  }
}

/* -------------------- Utility: band magnitudes -------------------- */

void computeBandMagnitudes(const double *fftMagnitudes, double *bands, uint8_t numBands) {
  const uint16_t binCount    = SAMPLES / 2;         /* 0..127 unique bins */
  const uint16_t binsPerBand = binCount / numBands; /* 128/16 = 8 */

  for (uint8_t b = 0; b < numBands; b++) {
    bands[b] = 0.0;
  }

  uint8_t bandIndex = 0;
  uint16_t binInBand = 0;

  /* Skip DC bin (k=0), start at k=1 */
  for (uint16_t k = 1; k < binCount; k++) {
    double mag = fftMagnitudes[k];
    bands[bandIndex] += mag;
    binInBand++;

    if (binInBand >= binsPerBand && bandIndex < numBands - 1) {
      bands[bandIndex] /= (double)binInBand;
      bandIndex++;
      binInBand = 0;
    }
  }

  if (binInBand > 0 && bandIndex < numBands) {
    bands[bandIndex] /= (double)binInBand;
  }
}

/* -------------------- Utility: dominant bin + interpolation -------------------- */

void findDominantPeak(const double *fftMagnitudes,
                      uint16_t binCount,
                      uint16_t &peakIndex,
                      double &peakValue,
                      double &avgValue) {
  peakIndex = 0;
  peakValue = 0.0;

  /* average over bins 2..(binCount-1) to avoid DC and very-low bins */
  double sum = 0.0;
  uint16_t count = 0;

  for (uint16_t k = 2; k < binCount; k++) {
    double mag = fftMagnitudes[k];
    sum += mag;
    count++;

    if (mag > peakValue) {
      peakValue = mag;
      peakIndex = k;
    }
  }

  avgValue = (count > 0) ? (sum / (double)count) : 0.0;
}

/*
  Parabolic interpolation around the peak bin to refine frequency estimate.
  Uses magnitudes at k-1, k, k+1:
    delta = 0.5*(a - c) / (a - 2b + c), clamped to [-0.5, 0.5]
*/
double parabolicPeakDelta(const double *fftMagnitudes, uint16_t k, uint16_t binCount) {
  if (k == 0 || k + 1 >= binCount) {
    return 0.0;
  }

  double a = fftMagnitudes[k - 1];
  double b = fftMagnitudes[k];
  double c = fftMagnitudes[k + 1];

  double denom = (a - 2.0 * b + c);
  if (fabs(denom) < 1e-12) {
    return 0.0;
  }

  double delta = 0.5 * (a - c) / denom;

  if (delta > 0.5) delta = 0.5;
  if (delta < -0.5) delta = -0.5;

  return delta;
}

/* -------------------- Utility: frequency -> MIDI -> note name -------------------- */

int frequencyToMidi(double freqHz) {
  if (freqHz <= 0.0) return -1;

  double midiFloat = 69.0 + 12.0 * (log(freqHz / 440.0) / log(2.0));
  int midiNote = (int)round(midiFloat);

  if (midiNote < 0 || midiNote > 127) return -1;
  return midiNote;
}

void midiToNoteNameSharps(int midiNote, char *out, size_t outLen) {
  if (outLen == 0) return;

  if (midiNote < 0 || midiNote > 127) {
    strncpy(out, "---", outLen);
    out[outLen - 1] = '\0';
    return;
  }

  static const char *names[12] = {
    "C", "C#", "D", "D#", "E", "F",
    "F#", "G", "G#", "A", "A#", "B"
  };

  const char *base = names[midiNote % 12];
  strncpy(out, base, outLen);
  out[outLen - 1] = '\0';
}

/* -------------------- Utility: drawing -------------------- */

void drawSpectrumAndPitch(double *bands,
                          uint8_t numBands,
                          bool quiet,
                          int midiToShow,
                          double freqToShowHz) {
  display.clearDisplay();
  display.setTextSize(1);
  display.setTextColor(WHITE);

  /* Top text line */
  display.setCursor(0, 0);
  char noteName[4] = "---";
  midiToNoteNameSharps(midiToShow, noteName, sizeof(noteName));

  display.print("Note:");
  display.print(noteName);
  display.print("  Freq:");
  if (midiToShow >= 0 && freqToShowHz > 0.0) {
    display.print((int)round(freqToShowHz));
    display.print("Hz");
  } else {
    display.print("---");
  }

  const uint8_t textHeight = 10;

  /* Quiet gate: keep the graph calm */
  if (quiet) {
    display.display();
    return;
  }

  /* Lowest band suppressed */
  bands[0] = 0.0;

  /* Update slow normalization reference (ignore band 0) */
  double maxNow = 1.0;
  for (uint8_t b = 1; b < numBands; b++) {
    if (bands[b] > maxNow) maxNow = bands[b];
  }

  maxRef *= MAXREF_DECAY;
  if (maxNow > maxRef) maxRef = maxNow;
  if (maxRef < 1.0) maxRef = 1.0;

  const uint8_t barWidth  = SCREEN_WIDTH / numBands;
  const uint8_t maxHeight = SCREEN_HEIGHT - 1 - textHeight;

  for (uint8_t b = 0; b < numBands; b++) {
    double norm = bands[b] / maxRef;
    if (norm < 0.0) norm = 0.0;
    if (norm > 1.0) norm = 1.0;

    /* Mild compression (helps keep quiet details visible without “breathing”) */
    double compressed = log10(1.0 + 4.0 * norm);
    norm = compressed;

    uint8_t barHeight = (uint8_t)(norm * (double)maxHeight);

    uint8_t x = b * barWidth;
    uint8_t y = SCREEN_HEIGHT - barHeight;
    uint8_t effectiveWidth = (barWidth > 1) ? barWidth - 1 : barWidth;

    display.fillRect(x, y, effectiveWidth, barHeight, WHITE);
  }

  display.display();
}

/* -------------------- setup & loop -------------------- */

void setup() {
  Serial.begin(115200);
  delay(200);

  analogReadResolution(12);
  analogRead(MIC_PIN);

  SPI.setSCK(OLED_CLK);
  SPI.setTX(OLED_MOSI);
  SPI.begin();

  if (!display.begin(0x3C)) {
    while (true) {
      delay(500);
    }
       }

  display.clearDisplay();
  display.setTextSize(1);
  display.setTextColor(WHITE);
  display.setCursor(0, 0);
  display.println("Pico2 FFT Analyzer");
  display.println("Quiet + Hysteresis");
  display.display();
  delay(800);
}

void loop() {
  static double bands[NUM_BANDS];

  /* 1) Sample audio */
  sampleAudioFrame();

  /* 2) FFT */
  FFT.windowing(vReal, SAMPLES, FFT_WIN_TYP_HAMMING, FFT_FORWARD);
  FFT.compute(vReal, vImag, SAMPLES, FFT_FORWARD);
  FFT.complexToMagnitude(vReal, vImag, SAMPLES);

  /* 3) Pitch detection on full-resolution bins (0..127) */
  uint16_t peakIndex = 0;
  double peakValue = 0.0;
  double avgValue = 0.0;

  findDominantPeak(vReal, SAMPLES / 2, peakIndex, peakValue, avgValue);

  double peakRatio = (avgValue > 1e-9) ? (peakValue / avgValue) : 0.0;

  /* Refine peak frequency with parabolic interpolation */
  double delta = parabolicPeakDelta(vReal, peakIndex, SAMPLES / 2);
  double refinedBin = (double)peakIndex + delta;
  double peakFreqHz = refinedBin * (SAMPLING_FREQUENCY / (double)SAMPLES);

  /* Confidence gating */
  bool pitchConfident = (peakValue > PEAK_MAG_THRESHOLD) &&
                        (peakRatio > PEAK_RATIO_THRESHOLD) &&
                        (peakFreqHz > 40.0) &&
                        (peakFreqHz < (SAMPLING_FREQUENCY / 2.0));

  /* 4) Band magnitudes for display bars */
  computeBandMagnitudes(vReal, bands, NUM_BANDS);

  /* 5) Quiet gating for the bar graph (average band energy) */
  double sumBands = 0.0;
  for (uint8_t b = 1; b < NUM_BANDS; b++) {
    sumBands += bands[b];
  }
  double frameEnergy = sumBands / (double)(NUM_BANDS - 1);

  bool quietGraph = (frameEnergy < QUIET_THRESHOLD);

  /* 6) Update pitch smoothing + note hysteresis */
  int midiDetected = -1;

  if (pitchConfident && !quietGraph) {
    /* Smooth frequency */
    if (smoothedFreqHz <= 0.0) {
      smoothedFreqHz = peakFreqHz;
    } else {
      smoothedFreqHz =
        (1.0 - FREQ_SMOOTH_ALPHA) * smoothedFreqHz +
        FREQ_SMOOTH_ALPHA * peakFreqHz;
    }

    midiDetected = frequencyToMidi(smoothedFreqHz);

    /* Candidate persistence hysteresis */
    if (midiDetected == candidateMidi) {
      if (candidateCount < 255) candidateCount++;
    } else {
      candidateMidi = midiDetected;
      candidateCount = 1;
    }

    if (candidateCount >= NOTE_STABLE_FRAMES && candidateMidi != currentMidi) {
      currentMidi = candidateMidi;
    }

    noteHoldCount = NOTE_HOLD_FRAMES;
  } else {
    /* No confident pitch: hold last note briefly, then clear */
    if (noteHoldCount > 0) {
      noteHoldCount--;
    } else {
      currentMidi = -1;
      candidateMidi = -1;
      candidateCount = 0;
      smoothedFreqHz = 0.0;
    }
  }

  /* 7) Draw */
  double freqToShow = (currentMidi >= 0) ? smoothedFreqHz : 0.0;
  drawSpectrumAndPitch(bands, NUM_BANDS, quietGraph, currentMidi, freqToShow);
}
