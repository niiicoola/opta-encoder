#include <cassert>
#include <cstdint>
#include <iostream>
#include "../firmware/opta_encoder_lan/SheetCounter.h"

static void clear(volatile SheetCounter &c, uint32_t now) {
  c.observe(false, now);
  c.poll(now + 2000);
}

static void present(volatile SheetCounter &c, uint32_t now) {
  c.observe(true, now);
  c.poll(now + 2000);
}

int main() {
  {
    volatile SheetCounter c;
    c.begin(false, 0, 2000, 2000, 10000000);
    c.poll(1999); assert(!c.armed);
    c.poll(2000); assert(c.armed);
    present(c, 10000); assert(c.total == 1 && !c.armed && !c.rateValid);
    for (uint32_t t = 20000; t < 1000000; t += 1000) c.poll(t);
    assert(c.total == 1); // Foglio fermo davanti al sensore.
    clear(c, 1100000);
    present(c, 1210000);
    assert(c.total == 2 && c.rateValid && c.intervalUs == 1200000);
    c.poll(11212000); assert(!c.rateValid);
    clear(c, 12000000); present(c, 12100000);
    assert(c.total == 3 && !c.rateValid);
    clear(c, 12500000); present(c, 13300000);
    assert(c.total == 4 && c.rateValid && c.intervalUs == 1200000);
  }
  {
    volatile SheetCounter c;
    c.begin(true, 0, 2000, 2000, 10000000);
    c.poll(100000); assert(c.total == 0 && !c.armed);
    clear(c, 110000); present(c, 120000); assert(c.total == 1);
  }
  {
    volatile SheetCounter c;
    c.begin(false, 0, 2000, 2000, 10000000);
    c.poll(2000);
    c.observe(true, 10000); c.observe(false, 10050); c.poll(20000);
    assert(c.total == 0 && c.rejectedPresent == 1 && c.armed);
    present(c, 30000); assert(c.total == 1);
    c.observe(false, 40000); c.observe(true, 40500); c.poll(50000);
    assert(c.total == 1 && c.rejectedClear == 1 && !c.armed);
    clear(c, 60000); present(c, 70000); assert(c.total == 2);
  }
  {
    // Tutti i fronti osservati: un timer di conferma in ritardo non perde il
    // foglio gia' transitato, a differenza del polling nel ciclo di rete.
    volatile SheetCounter c;
    c.begin(false, 0, 2000, 2000, 10000000);
    c.observe(true, 10000);
    c.observe(false, 20000);
    c.observe(true, 30000);
    c.observe(false, 40000);
    c.poll(100000);
    assert(c.total == 2 && c.intervalUs == 20000);
  }
  {
    // Non esiste una soglia adattiva: una perdita precedente non dimezza i
    // passaggi successivi e l'accelerazione non altera la soglia di accettazione.
    volatile SheetCounter c;
    c.begin(false, 0, 2000, 2000, 10000000); c.poll(2000);
    uint32_t t = 10000;
    for (unsigned i = 0; i < 50; ++i) {
      present(c, t); clear(c, t + 10000);
      t += i < 20 ? 100000 : 60000;
    }
    assert(c.total == 50);
  }
  {
    // Un minuto a 50 fogli/min, campionamento indipendente ogni millisecondo.
    volatile SheetCounter c;
    c.begin(false, 0, 2000, 2000, 10000000);
    for (uint32_t t = 0; t < 60010000; t += 1000) {
      const bool active = t >= 10000 && (t - 10000) % 1200000 < 500000;
      c.observe(active, t);
    }
    assert(c.total == 50 && c.rateValid && c.intervalUs == 1200000);
  }
  {
    volatile SheetCounter c;
    const uint32_t start = UINT32_MAX - 1000;
    c.begin(false, start, 2000, 2000, 10000000);
    c.poll(uint32_t(start + 2000));
    present(c, uint32_t(start + 10000));
    clear(c, uint32_t(start + 30000));
    present(c, uint32_t(start + 1210000));
    assert(c.total == 2 && c.rateValid && c.intervalUs == 1200000);
    // La scadenza del periodo evita una velocita' residua dopo una lunga sosta.
    c.poll(uint32_t(start + 12000000)); assert(!c.rateValid);
    c.total = UINT64_C(4294967296);
    clear(c, uint32_t(start + 13000000)); present(c, uint32_t(start + 13100000));
    assert(c.total == UINT64_C(4294967297));
  }
  std::cout << "Contafogli: avvio, sosta, filtri, timer, accelerazione, 50 fogli/min e wrap OK\n";
}
