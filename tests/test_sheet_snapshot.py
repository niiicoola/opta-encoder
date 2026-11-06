"""Contratto contafogli con un server OPC UA locale effettivo."""
import logging
from pathlib import Path
import socket
import sys
import unittest

from opcua import Client, Server, ua

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import read_sheet_counter_opcua as reader


class SheetSnapshotTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        logging.getLogger().setLevel(logging.ERROR)
        with socket.socket() as sock:
            sock.bind(("127.0.0.1", 0))
            port = sock.getsockname()[1]
        cls.endpoint = f"opc.tcp://127.0.0.1:{port}"
        cls.server = Server()
        cls.server.set_endpoint(cls.endpoint)
        cls.server.register_namespace("urn:test:unrelated")
        cls.ns = cls.server.register_namespace(reader.NAMESPACE)
        obj = cls.server.get_objects_node().add_object(cls.ns, "SheetCounter")
        fields = {
            "SheetCounter.TotalSheets": (9007199254740993, ua.VariantType.UInt64),
            "SheetCounter.SheetsPerMinute": (50.0, ua.VariantType.Double),
            "SheetCounter.RateValid": (True, ua.VariantType.Boolean),
            "SheetCounter.InputActive": (False, ua.VariantType.Boolean),
            "SheetCounter.Armed": (True, ua.VariantType.Boolean),
            "SheetCounter.ProfileId": ("real-sheets-heschen-pnp-diagnostic-v1", ua.VariantType.String),
            "SheetCounter.Simulation": (False, ua.VariantType.Boolean),
            "SheetCounter.TestMode": (True, ua.VariantType.Boolean),
            "SheetCounter.MeasurementValid": (False, ua.VariantType.Boolean),
            "SheetCounter.SampleSequence": (2, ua.VariantType.UInt32),
            "SheetCounter.InputTransitions": (100, ua.VariantType.UInt32),
            "SheetCounter.RejectedPresentPulses": (1, ua.VariantType.UInt32),
            "SheetCounter.RejectedClearPulses": (2, ua.VariantType.UInt32),
            "SheetCounter.PresentStableUs": (2000, ua.VariantType.UInt32),
            "SheetCounter.ClearStableUs": (2000, ua.VariantType.UInt32),
            "SheetCounter.IdleTimeoutMs": (10000, ua.VariantType.UInt32),
            "Device.AcquisitionMode": ("sheet_counter", ua.VariantType.String),
            "Device.BootId": ("test-boot", ua.VariantType.String),
            "Device.UptimeMs": (4294968000, ua.VariantType.UInt64),
            "Device.TimeSynchronized": (False, ua.VariantType.Boolean),
            "Device.MeasurementStatus": (1, ua.VariantType.UInt32),
        }
        cls.nodes = {name: obj.add_variable(ua.NodeId(name, cls.ns), name, ua.Variant(value, kind))
                     for name, (value, kind) in fields.items()}
        cls.server.start()
        cls.client = Client(cls.endpoint)
        cls.client.connect()

    @classmethod
    def tearDownClass(cls):
        cls.client.disconnect()
        cls.server.stop()

    def test_count_precision_and_namespace_resolution(self):
        self.assertNotEqual(self.ns, 2)
        sample = reader.snapshot(self.client, allow_test=True)
        self.assertEqual(sample["SheetCounter.TotalSheets"], "9007199254740993")
        self.assertEqual(sample["Device.UptimeMs"], "4294968000")
        self.assertEqual(sample["SheetCounter.SheetsPerMinute"], 50.0)
        self.assertNotIn("Encoder.NetPosition", sample)

    def test_test_measurements_are_rejected_by_default(self):
        with self.assertRaisesRegex(ValueError, "TEST NON VALIDATO"):
            reader.snapshot(self.client)

    def test_wrong_mode_is_rejected(self):
        node = self.nodes["Device.AcquisitionMode"]
        node.set_value("rotary_encoder")
        try:
            with self.assertRaisesRegex(ValueError, "Modalita"):
                reader.snapshot(self.client, allow_test=True)
        finally:
            node.set_value("sheet_counter")

    def test_updating_snapshot_is_rejected(self):
        node = self.nodes["SheetCounter.SampleSequence"]
        node.set_value(ua.Variant(3, ua.VariantType.UInt32))
        try:
            with self.assertRaisesRegex(RuntimeError, "coerente"):
                reader.snapshot(self.client, allow_test=True)
        finally:
            node.set_value(ua.Variant(2, ua.VariantType.UInt32))

    def test_bad_quality_does_not_become_zero(self):
        node = self.nodes["SheetCounter.TotalSheets"]
        bad = ua.DataValue(ua.Variant(0, ua.VariantType.UInt64))
        bad.StatusCode = ua.StatusCode(ua.StatusCodes.BadSensorFailure)
        node.set_data_value(bad)
        try:
            with self.assertRaises(ua.UaStatusCodeError):
                reader.snapshot(self.client, allow_test=True)
        finally:
            node.set_value(ua.Variant(9007199254740993, ua.VariantType.UInt64))

    def test_writes_rejected_and_diagnostics_bounded(self):
        remote = self.client.get_node(self.nodes["SheetCounter.TotalSheets"].nodeid)
        with self.assertRaises(ua.UaStatusCodeError):
            remote.set_value(ua.Variant(0, ua.VariantType.UInt64))
        original = self.client.uaclient.get_attributes
        sizes = []
        def bounded(nodes, attribute):
            sizes.append(len(nodes))
            self.assertLessEqual(len(nodes), reader.MAX_NODES_PER_READ)
            return original(nodes, attribute)
        self.client.uaclient.get_attributes = bounded
        try:
            sample = reader.snapshot(self.client, allow_test=True, diagnostics=True)
            self.assertEqual(sizes, [8, 8, 3])
            self.assertEqual(sample["SheetCounter.RejectedClearPulses"], 2)
        finally:
            self.client.uaclient.get_attributes = original


if __name__ == "__main__":
    unittest.main()
