"""Vincoli di profilo, pacchetto e verifica remota del contafogli."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import struct
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import opta_profiles
import provision_opta as provision

ROOT = Path(__file__).resolve().parents[1]


class SheetProvisionTest(unittest.TestCase):
    def setUp(self):
        self.profile = opta_profiles.load_profile("heschen-e3f-ds10p3-sheets")
        self.device = json.loads((ROOT / "devices/example-sheets.json").read_text())
        self.state = {"firmware": "0.4.0-lan", "boot_id": "a" * 32, "ota_ready": True,
                      "acquisition_mode": "sheet_counter", "profile_id": self.profile["firmware_profile_id"]}
        first = {"Device.BootId": "a" * 32, "Device.AcquisitionMode": "sheet_counter",
                 "Device.UptimeMs": "1000", "SheetCounter.TotalSheets": "10",
                 "SheetCounter.ProfileId": self.profile["firmware_profile_id"],
                 "SheetCounter.Simulation": False, "SheetCounter.TestMode": True,
                 "SheetCounter.MeasurementValid": False, "SheetCounter.RejectedPresentPulses": 0,
                 "SheetCounter.RejectedClearPulses": 0}
        self.samples = [first, {**first, "Device.UptimeMs": "2000", "SheetCounter.TotalSheets": "11"}]

    def test_profile_generates_only_sheet_settings_and_validates_device(self):
        device, profile = provision.load_device(ROOT / "devices/example-sheets.json")
        self.assertEqual(opta_profiles.acquisition_mode(profile), "sheet_counter")
        header = opta_profiles.profile_header(profile)
        self.assertIn("#define GERP_MODE_SHEETS 1", header)
        self.assertIn("#define GERP_SHEET_PRESENT_US 2000u", header)
        self.assertNotIn("GERP_ENCODER_PPR", header)
        self.assertEqual(device["encoder_profile"], profile["profile_id"])

    def test_invalid_timings_modes_and_rotary_fields_are_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "profiles").mkdir()
            path = root / "profiles" / (self.profile["profile_id"] + ".json")
            for key, value in (("present_stable_us", 0), ("clear_stable_us", True),
                               ("idle_timeout_ms", 10000000), ("active_high", 1),
                               ("acquisition_mode", "unknown"), ("pulses_per_revolution", 50),
                               ("max_sheets_per_minute_nominal", -1)):
                path.write_text(json.dumps({**self.profile, key: value}))
                with self.subTest(key=key), self.assertRaises(ValueError):
                    opta_profiles.load_profile(self.profile["profile_id"], root)

    def test_sheet_count_does_not_become_distance(self):
        result = provision.assess_samples(self.device, self.profile, self.state, self.samples, self.state)
        self.assertEqual(result["sheet_count"], "11")
        self.assertEqual(result["total"], "11")
        self.assertIsNone(result["position"])
        self.assertEqual(result["acquisition_mode"], "sheet_counter")
        self.assertNotIn("invalid_transitions", result)

    def test_wrong_mode_reboot_stale_samples_and_counter_reset_fail_verification(self):
        for key, value in (("Device.AcquisitionMode", "rotary_encoder"),
                           ("Device.BootId", "b" * 32), ("Device.UptimeMs", "1000"),
                           ("SheetCounter.TotalSheets", "9"), ("SheetCounter.Simulation", True),
                           ("SheetCounter.MeasurementValid", True),
                           ("SheetCounter.ProfileId", "different"),
                           ("SheetCounter.RejectedPresentPulses", -1)):
            changed = deepcopy(self.samples)
            changed[-1][key] = value
            with self.subTest(key=key), self.assertRaises(ValueError):
                provision.assess_samples(self.device, self.profile, self.state, changed, self.state)
        for key, value in (("acquisition_mode", "rotary_encoder"), ("profile_id", "different")):
            with self.subTest(key=key), self.assertRaises(ValueError):
                provision.assess_samples(self.device, self.profile, self.state, self.samples,
                                         {**self.state, key: value})

    def test_release_checks_acquisition_mode(self):
        with tempfile.TemporaryDirectory() as temp:
            directory = Path(temp)
            content = (struct.pack("<II", 0x24080000, 0x08040041) + b"GERP_OPTA_OTA_V1\0"
                       + b"0.4.0-lan\0" + self.profile["firmware_profile_id"].encode() + b"\0" + bytes(400))
            (directory / "firmware.bin").write_bytes(content)
            manifest = {"version": "0.4.0-lan", "board": provision.FQBN,
                        "encoder_profile": self.profile["profile_id"], "qualification": "diagnostic_only",
                        "counts_per_revolution": None, "acquisition_mode": "sheet_counter",
                        "firmware_profile_id": self.profile["firmware_profile_id"],
                        "bytes": len(content), "sha256": hashlib.sha256(content).hexdigest()}
            path = directory / "manifest.json"
            path.write_text(json.dumps(manifest))
            provision.check_release(directory, self.device)
            manifest["acquisition_mode"] = "rotary_encoder"
            path.write_text(json.dumps(manifest))
            with self.assertRaises(ValueError):
                provision.check_release(directory, self.device)


if __name__ == "__main__":
    unittest.main()
