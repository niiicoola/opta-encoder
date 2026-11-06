#pragma once
#include <chrono>
#include "EncoderProfile.h"
#include "Quadrature.h"
#include "SheetCounter.h"

static constexpr pin_size_t INPUT_A = A0; // I1: fase A oppure uscita PNP NO
static constexpr pin_size_t INPUT_B = A1; // I2: solo fase B dell'encoder

struct AcquisitionData {
  int64_t position = 0;
  uint64_t total = 0;
  uint32_t edgesA = 0, edgesB = 0, invalid = 0;
  uint32_t transitions = 0, rejectedPresent = 0, rejectedClear = 0, intervalUs = 0;
  bool levelA = false, levelB = false, active = false, armed = false, rateValid = false;
};

#if GERP_MODE_SHEETS
static volatile SheetCounter sheetCounter;
static mbed::Ticker sheetTicker;

static bool sheetActive() {
  return (digitalRead(INPUT_A) == HIGH) == bool(GERP_SHEET_ACTIVE_HIGH);
}

static void onSheetChange() {
  core_util_critical_section_enter();
  sheetCounter.observe(sheetActive(), micros());
  core_util_critical_section_exit();
}

static void onSheetTimer() {
  core_util_critical_section_enter();
  // Anche il timer legge l'ingresso: il conteggio non dipende dal ciclo di rete.
  sheetCounter.observe(sheetActive(), micros());
  core_util_critical_section_exit();
}
#else
static volatile Quadrature decoder;

static uint8_t readAB() {
  return (digitalRead(INPUT_A) == HIGH ? 2 : 0) |
         (digitalRead(INPUT_B) == HIGH ? 1 : 0);
}

static void onEncoderChange() { decoder.observe(readAB()); }
#endif

static void acquisitionStart() {
  pinMode(INPUT_A, INPUT);
  pinMode(INPUT_B, INPUT);
#if GERP_MODE_SHEETS
  sheetCounter.begin(sheetActive(), micros(), GERP_SHEET_PRESENT_US,
                     GERP_SHEET_CLEAR_US, GERP_SHEET_IDLE_MS * 1000u);
  attachInterrupt(digitalPinToInterrupt(INPUT_A), onSheetChange, CHANGE);
  sheetTicker.attach(onSheetTimer, std::chrono::milliseconds(1));
#else
  decoder.begin(readAB());
  attachInterrupt(digitalPinToInterrupt(INPUT_A), onEncoderChange, CHANGE);
  attachInterrupt(digitalPinToInterrupt(INPUT_B), onEncoderChange, CHANGE);
#endif
}

static AcquisitionData acquisitionSnapshot() {
  AcquisitionData result;
  core_util_critical_section_enter();
#if GERP_MODE_SHEETS
  result.total = sheetCounter.total;
  result.active = sheetCounter.rawActive;
  result.armed = sheetCounter.armed;
  result.rateValid = sheetCounter.rateValid;
  result.intervalUs = sheetCounter.intervalUs;
  result.transitions = sheetCounter.transitions;
  result.rejectedPresent = sheetCounter.rejectedPresent;
  result.rejectedClear = sheetCounter.rejectedClear;
#else
  result.position = decoder.position;
  result.total = decoder.total;
  result.edgesA = decoder.edgesA;
  result.edgesB = decoder.edgesB;
  result.invalid = decoder.invalid;
  const uint8_t ab = readAB();
  result.levelA = (ab & 2) != 0;
  result.levelB = (ab & 1) != 0;
#endif
  core_util_critical_section_exit();
  return result;
}
