/* photoresistors organ
output formatted for Max/MSP patch
This is the program for MTML 2024, updated May 2025 by Paul V. Miller

Use "calibration" code to calibrate the 5 analog inputs while button is depressed.
while button is depressed, you enter calibration mode
*/

int photoPin1 = A0;
int photoPin2 = A1;
int photoPin3 = A2;
int photoPin4 = A3;
int photoPin5 = A4;

const int buttonPin = 2;  // button connected to digital pin 2
const int ledPin = 13;    // this is the built-in LED

int buttonState = 0;

int photoPin1Min = 1023;
int photoPin1Max = 0;
int photoPin2Min = 1023;
int photoPin2Max = 0;
int photoPin3Min = 1023;
int photoPin3Max = 0;
int photoPin4Min = 1023;
int photoPin4Max = 0;
int photoPin5Min = 1023;
int photoPin5Max = 0;

void setup() {
  Serial.begin(9600);
  pinMode(buttonPin, INPUT);
  pinMode(ledPin, OUTPUT);

  // attachInterrupt(digitalPinToInterrupt (buttonPin), calibratePhotoresistors, RISING);

}

void loop() {

  int light1 = analogRead(photoPin1);
  int light2 = analogRead(photoPin2);
  int light3 = analogRead(photoPin3);
  int light4 = analogRead(photoPin4);
  int light5 = analogRead(photoPin5);

  buttonState = digitalRead(buttonPin);

  if (buttonState == HIGH) {
    digitalWrite(ledPin, HIGH); // turn LED on
    // calibrate!
    if (light1 > photoPin1Max) {
      photoPin1Max = light1;
    }
    if (light1 < photoPin1Min) {
      photoPin1Min = light1;
    }
    if (light2 > photoPin2Max) {
      photoPin2Max = light2;
    }
    if (light2 < photoPin2Min) {
      photoPin2Min = light2;
    }
    if (light3 > photoPin3Max) {
      photoPin3Max = light3;
    }
    if (light3 < photoPin3Min) {
      photoPin3Min = light3;
    }
    if (light4 > photoPin4Max) {
      photoPin4Max = light4;
    }
    if (light4 < photoPin4Min) {
      photoPin4Min = light4;
    }
    if (light5 > photoPin5Max) {
      photoPin5Max = light5;
    }
    if (light5 < photoPin5Min) {
      photoPin5Min = light5;
    }

  } else {
    digitalWrite(ledPin, LOW);  // turn LED off
  }

  light1 = constrain(light1, photoPin1Min, photoPin1Max);
  light1 = map(light1, photoPin1Min, photoPin1Max, 0, 255);

  light2 = constrain(light2, photoPin2Min, photoPin2Max);
  light2 = map(light2, photoPin2Min, photoPin2Max, 0, 255);

  light3 = constrain(light3, photoPin3Min, photoPin3Max);
  light3 = map(light3, photoPin3Min, photoPin3Max, 0, 255);

  light4 = constrain(light4, photoPin4Min, photoPin4Max);
  light4 = map(light4, photoPin4Min, photoPin4Max, 0, 255);

  light5 = constrain(light5, photoPin5Min, photoPin5Max);
  light5 = map(light5, photoPin5Min, photoPin5Max, 0, 255);

  Serial.print(light1);
  Serial.print(" ");
  Serial.print(light2);
  Serial.print(" ");
  Serial.print(light3);
  Serial.print(" ");
  Serial.print(light4);
  Serial.print(" ");
  Serial.print(light5);
  Serial.println();

  delay(50);
}
