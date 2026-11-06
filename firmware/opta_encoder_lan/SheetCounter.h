#pragma once
#include <stdint.h>

// Logica pura: chiamare observe() sui fronti e poll() da un timer periodico.
// Il primo foglio viene contato solo dopo una condizione di assenza stabile.
struct SheetCounter {
  uint64_t total = 0;
  uint32_t transitions = 0;
  uint32_t rejectedPresent = 0;
  uint32_t rejectedClear = 0;
  bool rawActive = false;
  bool armed = false;
  bool rateValid = false;
  uint32_t intervalUs = 0;

  void begin(bool active, uint32_t now, uint32_t presentUs,
             uint32_t clearUs, uint32_t idleUs) volatile {
    rawActive = active;
    candidateSince = now;
    presentStableUs = presentUs;
    clearStableUs = clearUs;
    idleTimeoutUs = idleUs;
    settled = false;
    armed = false;
    hasPreviousCount = false;
    rateValid = false;
  }

  void poll(uint32_t now) volatile {
    // Il timer chiude la finestra della velocita' durante le soste, prima del
    // wrap di micros(). Le differenze unsigned gestiscono il wrap ordinario.
    if (hasPreviousCount && uint32_t(now - lastCountUs) >= idleTimeoutUs) {
      hasPreviousCount = false;
      rateValid = false;
    }
    if (settled || uint32_t(now - candidateSince) <
        (rawActive ? presentStableUs : clearStableUs)) return;
    settled = true;
    if (!rawActive) {
      armed = true;
      return;
    }
    if (!armed) return;
    armed = false;
    const uint32_t countedAt = candidateSince + presentStableUs;
    if (hasPreviousCount) {
      intervalUs = uint32_t(countedAt - lastCountUs);
      rateValid = intervalUs > 0 && intervalUs < idleTimeoutUs;
    }
    lastCountUs = countedAt;
    hasPreviousCount = true;
    ++total;
  }

  void observe(bool active, uint32_t now) volatile {
    // Conferma anche un impulso terminato tra due tick, se i fronti sono stati
    // acquisiti e la durata minima e' stata rispettata.
    poll(now);
    if (active == rawActive) return;
    if (!settled) {
      if (rawActive) ++rejectedPresent;
      else ++rejectedClear;
    }
    ++transitions;
    rawActive = active;
    candidateSince = now;
    settled = false;
  }

 private:
  uint32_t presentStableUs = 0;
  uint32_t clearStableUs = 0;
  uint32_t idleTimeoutUs = 0;
  uint32_t candidateSince = 0;
  uint32_t lastCountUs = 0;
  bool settled = false;
  bool hasPreviousCount = false;
};
