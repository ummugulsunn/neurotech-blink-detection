// Single-channel EOG/EEG acquisition for blink detection.
//
// Samples one analog pin at a fixed rate and streams "board_time_us,adc_value"
// lines over serial. All filtering and detection happens on the host in Python.
//
// Board: Arduino Uno R3 (10-bit ADC, 0-1023 for 0-5 V).

const uint8_t  SIGNAL_PIN        = A0;       // analog output of the biopotential amplifier
const uint32_t SAMPLE_RATE_HZ    = 250;      // must match --fs on the host side
const uint32_t BAUD_RATE         = 115200;   // must match --baud on the host side
const uint32_t SAMPLE_PERIOD_US  = 1000000UL / SAMPLE_RATE_HZ;

uint32_t nextSampleUs = 0;

void setup() {
  Serial.begin(BAUD_RATE);
  // Header line so the host can check the configuration.
  Serial.print(F("# fs_hz="));
  Serial.print(SAMPLE_RATE_HZ);
  Serial.print(F(" pin=A0 baud="));
  Serial.println(BAUD_RATE);
  nextSampleUs = micros();
}

void loop() {
  uint32_t now = micros();
  // Signed difference keeps this correct across the ~70 min micros() rollover.
  if ((int32_t)(now - nextSampleUs) < 0) {
    return;
  }
  nextSampleUs += SAMPLE_PERIOD_US;

  int value = analogRead(SIGNAL_PIN);
  Serial.print(now);
  Serial.print(',');
  Serial.println(value);
}
