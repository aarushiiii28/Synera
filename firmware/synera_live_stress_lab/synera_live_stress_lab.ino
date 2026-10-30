// SYNERA Live Stress Lab firmware (Arduino Uno)
//
// Sends one newline-delimited CSV line about every 2 seconds at 9600 baud:
//
//     time_ms,temperature_C,humidity_pct,gas_raw
//     2000,26.0,57.0,67
//
// * temperature / humidity: DHT11. If the DHT11 does not answer, both fields are left EMPTY (2000,,,67). The software then records them as
//   missing; nothing is guessed.
// * gas_raw: the raw 10-bit ADC value (0..1023) of an MQ-series analog output. It is NOT ppm, NOT AQI and NOT PM2.5.
//
// Wiring (check the labels printed on your modules; the pin order differs between gas modules):
//   DHT11 : VCC -> 5V, GND -> GND, OUT -> D2
//   Gas   : VCC -> 5V, GND -> GND, AO  -> A0   (DO is not used)
// Keep pins D0 and D1 free: they are the USB serial line.
//
// The DHT11 is read by hand, so no library is needed. Only the DHT pin is ever driven.

const int DHT_PIN = 2;          // change here if your DHT11 is on another digital pin
const int GAS_PIN = A0;         // change here if the gas module's AO is on another analog pin
const unsigned long INTERVAL_MS = 2000;

// Returns 0 on success, otherwise an error code. DHT11 frame: 8-bit RH integer, RH decimal, temperature integer, temperature decimal, checksum.
int readDht11(float &hum, float &temp) {
  uint8_t d[5] = {0, 0, 0, 0, 0};
  pinMode(DHT_PIN, OUTPUT); digitalWrite(DHT_PIN, LOW); delay(20);
  digitalWrite(DHT_PIN, HIGH); delayMicroseconds(40); pinMode(DHT_PIN, INPUT_PULLUP);
  unsigned long t = micros();
  while (digitalRead(DHT_PIN) == HIGH) if (micros() - t > 200) return 1;     // no answer
  t = micros(); while (digitalRead(DHT_PIN) == LOW)  if (micros() - t > 200) return 2;
  t = micros(); while (digitalRead(DHT_PIN) == HIGH) if (micros() - t > 200) return 3;
  for (int i = 0; i < 40; i++) {
    t = micros(); while (digitalRead(DHT_PIN) == LOW)  if (micros() - t > 200) return 4;
    unsigned long start = micros(); while (digitalRead(DHT_PIN) == HIGH) if (micros() - start > 200) return 5;
    d[i / 8] <<= 1; if (micros() - start > 40) d[i / 8] |= 1;
  }
  if ((uint8_t)(d[0] + d[1] + d[2] + d[3]) != d[4]) return 6;               // checksum mismatch: the frame is corrupt
  hum = d[0] + d[1] / 10.0; temp = d[2] + d[3] / 10.0;
  return 0;
}

void setup() {
  Serial.begin(9600);
  delay(1000);
  Serial.println(F("# device=synera-uno-dht11-mq"));
  Serial.println(F("time_ms,temperature_C,humidity_pct,gas_raw"));
}

void loop() {
  unsigned long started = millis();
  float h = 0, t = 0;
  bool ok = (readDht11(h, t) == 0);
  int gas = analogRead(GAS_PIN);
  Serial.print(millis()); Serial.print(',');
  if (ok) { Serial.print(t, 1); Serial.print(','); Serial.print(h, 1); } else { Serial.print(','); }
  Serial.print(','); Serial.println(gas);
  unsigned long spent = millis() - started;
  if (spent < INTERVAL_MS) delay(INTERVAL_MS - spent);
}
