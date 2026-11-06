"""Lettura coerente e controlli di qualita' condivisi fra acquisizioni Opta."""
from opcua import ua

MAX_NODES_PER_READ = 8


def read_good(node):
    value = node.get_data_value()
    value.StatusCode.check()
    return value.Value.Value


def coherent_snapshot(client, namespace_uri, fields, prefix, integer_fields,
                      allow_simulation=False, allow_test=False, expected_mode=None):
    namespace = client.get_namespace_index(namespace_uri)
    node = lambda name: client.get_node(ua.NodeId(name, namespace))
    boot_node = node("Device.BootId")
    sequence_node = node(f"{prefix}.SampleSequence")
    for _ in range(5):
        boot_before = read_good(boot_node)
        before = read_good(sequence_node)
        if before % 2:
            continue
        nodes = [node(name) for name in fields]
        values = []
        for offset in range(0, len(nodes), MAX_NODES_PER_READ):
            batch = nodes[offset:offset + MAX_NODES_PER_READ]
            received = client.uaclient.get_attributes([n.nodeid for n in batch], ua.AttributeIds.Value)
            if len(received) != len(batch):
                raise ValueError("Risposta OPC UA incompleta")
            values.extend(received)
        result = {}
        for name, value in zip(fields, values):
            value.StatusCode.check()
            result[name] = value.Value.Value
        after = read_good(sequence_node)
        boot_after = read_good(boot_node)
        if before != after or after % 2 or boot_before != boot_after:
            continue
        if expected_mode and result.get("Device.AcquisitionMode") != expected_mode:
            raise ValueError("Modalita' di acquisizione inattesa")
        simulation = result[f"{prefix}.Simulation"]
        if simulation and not allow_simulation:
            raise ValueError("SIMULAZIONE: dati esclusi dalla produzione; usare --allow-simulation per il test")
        if not simulation and (result[f"{prefix}.TestMode"] or not result[f"{prefix}.MeasurementValid"]) and not allow_test:
            raise ValueError("TEST NON VALIDATO: dati esclusi dalla produzione; usare --allow-test per la diagnostica")
        result["Device.BootId"] = boot_after
        result[f"{prefix}.SampleSequence"] = after
        for name in integer_fields:
            result[name] = str(result[name])
        return result
    raise RuntimeError("Impossibile ottenere un campione coerente; ripetere la lettura")
