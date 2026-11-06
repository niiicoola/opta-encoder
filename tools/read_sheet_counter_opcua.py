#!/usr/bin/env python3
"""Legge il contafogli OPC UA senza azzerare o scrivere sul dispositivo."""
import argparse
import json
import logging
import sys
import time

from opcua import Client
from opcua_snapshot import MAX_NODES_PER_READ, coherent_snapshot

NAMESPACE = "urn:gerp:sheet-counter:v1"
FIELDS = (
    "SheetCounter.TotalSheets", "SheetCounter.SheetsPerMinute", "SheetCounter.RateValid",
    "SheetCounter.InputActive", "SheetCounter.Armed", "SheetCounter.ProfileId",
    "SheetCounter.Simulation", "SheetCounter.TestMode", "SheetCounter.MeasurementValid",
    "Device.AcquisitionMode", "Device.UptimeMs", "Device.TimeSynchronized",
)
DIAGNOSTICS = (
    "SheetCounter.InputTransitions", "SheetCounter.RejectedPresentPulses", "SheetCounter.RejectedClearPulses",
    "SheetCounter.PresentStableUs", "SheetCounter.ClearStableUs", "SheetCounter.IdleTimeoutMs",
    "Device.MeasurementStatus",
)


def snapshot(client, allow_simulation=False, allow_test=False, diagnostics=False):
    return coherent_snapshot(client, NAMESPACE, FIELDS + (DIAGNOSTICS if diagnostics else ()), "SheetCounter",
                             ("SheetCounter.TotalSheets", "Device.UptimeMs"), allow_simulation, allow_test,
                             expected_mode="sheet_counter")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("endpoint", help="opc.tcp://IP_OPTA:4840")
    parser.add_argument("--allow-test", action="store_true")
    parser.add_argument("--allow-simulation", action="store_true")
    parser.add_argument("--diagnostics", action="store_true")
    parser.add_argument("--samples", type=int, default=3)
    parser.add_argument("--interval", type=float, default=1)
    args = parser.parse_args()
    if args.samples < 1 or args.interval < 0:
        parser.error("samples deve essere positivo e interval non negativo")
    logging.basicConfig(level=logging.ERROR)
    client = Client(args.endpoint, timeout=5)
    connected = False
    try:
        client.connect()
        connected = True
        for index in range(args.samples):
            if index:
                time.sleep(args.interval)
            print(json.dumps(snapshot(client, args.allow_simulation, args.allow_test, args.diagnostics)), flush=True)
        return 0
    except Exception as exc:
        print(json.dumps({"error": str(exc) or type(exc).__name__}), file=sys.stderr)
        return 1
    finally:
        if connected:
            try:
                client.disconnect()
            except Exception:
                pass


if __name__ == "__main__":
    raise SystemExit(main())
