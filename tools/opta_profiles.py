"""Profili diagnostici di acquisizione: encoder A/B o contafogli."""
import json
from pathlib import Path
import re

from opta_project import ROOT


def acquisition_mode(profile):
    # I profili storici privi del campo restano encoder rotativi x4.
    return profile.get("acquisition_mode", "rotary_encoder")


def load_profile(identifier, root=None):
    if not isinstance(identifier, str) or not re.fullmatch(r"[a-z0-9][a-z0-9-]{0,95}", identifier):
        raise ValueError("Identificativo profilo encoder non valido")
    profile = json.loads(((root or ROOT) / "profiles" / f"{identifier}.json").read_text())
    if (not isinstance(profile, dict) or profile.get("schema_version") != 1 or profile.get("profile_id") != identifier
            or profile.get("compatible_board") != "AFX00003" or profile.get("qualification") != "diagnostic_only"):
        raise ValueError("Profilo non compatibile con Opta Lite diagnostico")
    mode = acquisition_mode(profile)
    if mode == "rotary_encoder":
        ppr, counts, multiplier = (profile.get(name) for name in
                                  ("pulses_per_revolution", "counts_per_revolution", "decoding_multiplier"))
        if (type(ppr) is not int or not 1 <= ppr <= 1000000 or type(multiplier) is not int or multiplier != 4
                or type(counts) is not int or counts != ppr * multiplier):
            raise ValueError("Il decoder implementa x4: PPR e conteggi/giro devono essere coerenti")
    elif mode == "sheet_counter":
        if any(name in profile for name in ("pulses_per_revolution", "counts_per_revolution", "decoding_multiplier")):
            raise ValueError("Il profilo contafogli non deve dichiarare impulsi o conteggi per giro")
        if type(profile.get("active_high")) is not bool:
            raise ValueError("Polarita' contafogli non valida")
        for field in ("present_stable_us", "clear_stable_us"):
            if type(profile.get(field)) is not int or not 1000 <= profile[field] <= 1000000:
                raise ValueError(f"{field}: usare da 1000 a 1000000 microsecondi")
        idle = profile.get("idle_timeout_ms")
        if type(idle) is not int or not 1000 <= idle <= 60000:
            raise ValueError("idle_timeout_ms: usare da 1000 a 60000 millisecondi")
        if idle * 1000 <= max(profile["present_stable_us"], profile["clear_stable_us"]):
            raise ValueError("Il timeout di inattivita' deve superare i filtri")
        nominal = profile.get("max_sheets_per_minute_nominal")
        if type(nominal) is not int or not 1 <= nominal <= 10000:
            raise ValueError("Velocita' nominale contafogli non valida")
    else:
        raise ValueError("Modalita' di acquisizione non supportata")
    firmware_id = profile.get("firmware_profile_id")
    if not isinstance(firmware_id, str) or not re.fullmatch(r"[A-Za-z0-9._-]{1,127}", firmware_id):
        raise ValueError("Identificativo OPC UA del profilo non valido")
    return profile


def profile_header(profile):
    mode = acquisition_mode(profile)
    common = ("#pragma once\n// Generato dal profilo della release; non modificare manualmente.\n"
              f"#define GERP_ACQUISITION_MODE {json.dumps(mode)}\n"
              f"#define GERP_MODE_SHEETS {int(mode == 'sheet_counter')}\n"
              f"#define GERP_ACQUISITION_PROFILE_ID {json.dumps(profile['firmware_profile_id'])}\n")
    if mode == "sheet_counter":
        return (common + f"#define GERP_SHEET_ACTIVE_HIGH {int(profile['active_high'])}\n"
                f"#define GERP_SHEET_PRESENT_US {profile['present_stable_us']}u\n"
                f"#define GERP_SHEET_CLEAR_US {profile['clear_stable_us']}u\n"
                f"#define GERP_SHEET_IDLE_MS {profile['idle_timeout_ms']}u\n")
    return (common +
            f"#define GERP_ENCODER_PPR {profile['pulses_per_revolution']}u\n"
            f"#define GERP_ENCODER_COUNTS_PER_REVOLUTION {profile['counts_per_revolution']}u\n"
            f"#define GERP_ENCODER_PROFILE_ID {json.dumps(profile['firmware_profile_id'])}\n"
            'static_assert(GERP_ENCODER_COUNTS_PER_REVOLUTION == GERP_ENCODER_PPR * 4u, "Decoder x4 richiesto");\n')
