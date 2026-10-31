"""Portable, standard-library-only validator for underline.motor-test-package/1.

The Underline exporter owns this implementation. Consumers may vendor an exact,
attributed, hash-pinned copy with the schema and golden fixtures.
"""

from __future__ import annotations

import hashlib
import json
import math
import struct
from pathlib import Path
from typing import Any

SCHEMA_ID = "underline.motor-test-package/1"
MAX_BYTES = 32 * 1024 * 1024
MAX_SAMPLES = 250_000
MAX_DEPTH = 24


class MotorPackageError(ValueError):
    def __init__(self, code: str, path: str, message: str) -> None:
        self.code, self.path = code, path
        super().__init__(f"{code} at {path}: {message}")


def _fail(code: str, path: str, message: str) -> None:
    raise MotorPackageError(code, path, message)


def _object(value: Any, keys: set[str], path: str) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != keys:
        _fail("STRUCTURE", path, f"Expected exactly these fields: {sorted(keys)}")
    return value


def _number(value: Any, path: str, *, positive: bool = False) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        _fail("NUMBER", path, "Expected a finite number, not a boolean")
    try:
        result = float(value)
    except OverflowError:
        _fail("NUMBER", path, "Number exceeds binary64 range")
    if not math.isfinite(result) or (positive and result <= 0):
        _fail("NUMBER", path, "Expected a finite positive number" if positive else "Nonfinite")
    return result


def _text(value: Any, path: str, *, nullable: bool = False) -> None:
    if nullable and value is None:
        return
    if not isinstance(value, str) or not value or len(value) > 4096:
        _fail("TEXT", path, "Expected nonempty text, at most 4096 characters")


def _hash(value: Any, path: str) -> None:
    if (
        not isinstance(value, str)
        or len(value) != 64
        or any(c not in "0123456789abcdef" for c in value)
    ):
        _fail("HASH", path, "Expected lowercase SHA-256 hex")


def _bounded(value: Any, depth: int = 0) -> None:
    if depth > MAX_DEPTH:
        _fail("LIMIT", "$", "Maximum nesting depth exceeded")
    if isinstance(value, dict):
        if len(value) > 512 or any(not isinstance(k, str) or len(k) > 4096 for k in value):
            _fail("LIMIT", "$", "Object/key limit exceeded")
        for item in value.values():
            _bounded(item, depth + 1)
    elif isinstance(value, list):
        if len(value) > MAX_SAMPLES:
            _fail("LIMIT", "$", "Array limit exceeded")
        for item in value:
            _bounded(item, depth + 1)
    elif isinstance(value, str):
        if len(value) > 4096:
            _fail("LIMIT", "$", "String limit exceeded")
    elif value is not None and not isinstance(value, bool):
        _number(value, "$")


def _digest_feed(digest: Any, value: Any) -> None:
    # Versioned, language-neutral encoding: numbers are IEEE754 binary64 big endian.
    if value is None:
        digest.update(b"Z")
    elif isinstance(value, bool):
        digest.update(b"T" if value else b"F")
    elif isinstance(value, (int, float)):
        number = _number(value, "$")
        digest.update(b"N" + struct.pack(">d", 0.0 if number == 0 else number))
    elif isinstance(value, str):
        data = value.encode("utf-8")
        digest.update(b"S" + struct.pack(">I", len(data)) + data)
    elif isinstance(value, list):
        digest.update(b"L" + struct.pack(">I", len(value)))
        for item in value:
            _digest_feed(digest, item)
    elif isinstance(value, dict):
        digest.update(b"D" + struct.pack(">I", len(value)))
        for key in sorted(value, key=lambda k: k.encode("utf-8")):
            _digest_feed(digest, key)
            _digest_feed(digest, value[key])
    else:
        _fail("STRUCTURE", "$", "Unsupported JSON value")


def MotorPackage_Digest(payload: dict[str, Any]) -> str:
    """Hash all fields except content_sha256; export dates are deliberately absent."""
    _bounded(payload)
    digest = hashlib.sha256(b"underline.motor-test-package/1\0")
    _digest_feed(digest, {k: v for k, v in payload.items() if k != "content_sha256"})
    return digest.hexdigest()


def _curve(value: Any, path: str) -> tuple[list[float], list[float]]:
    if not isinstance(value, dict):
        _fail("STRUCTURE", path, "Expected a curve object")
    time, thrust = value.get("time_s"), value.get("thrust_n")
    if (
        not isinstance(time, list)
        or not isinstance(thrust, list)
        or not 2 <= len(time) <= MAX_SAMPLES
        or len(time) != len(thrust)
    ):
        _fail("LENGTH", path, "Equal curve lengths of 2..250000 samples required")
    for index, (t, f) in enumerate(zip(time, thrust, strict=True)):
        _number(t, f"{path}.time_s[{index}]")
        _number(f, f"{path}.thrust_n[{index}]")
        if index and t <= time[index - 1]:
            _fail("CLOCK", f"{path}.time_s[{index}]", "Time must strictly increase")
    return time, thrust


def MotorPackage_Validate(payload: Any) -> dict[str, Any]:
    _bounded(payload)
    _object(
        payload,
        {
            "schema_id",
            "schema_version",
            "producer",
            "project",
            "motor",
            "source",
            "processing_chain",
            "calibration",
            "time",
            "evidence_curve",
            "simulation_curve",
            "diagnostics",
            "metrics",
            "content_sha256",
        },
        "$",
    )
    if (
        payload["schema_id"] != SCHEMA_ID
        or type(payload["schema_version"]) is not int
        or payload["schema_version"] != 1
    ):
        _fail("VERSION", "$.schema_id", "Unsupported motor package version")
    producer = _object(
        payload["producer"],
        {
            "application",
            "application_version",
            "exporter_id",
            "exporter_version",
            "plugin_api_version",
        },
        "$.producer",
    )
    for key, value in producer.items():
        _text(value, "$.producer." + key)
    _object(payload["project"], {"name"}, "$.project")
    _text(payload["project"]["name"], "$.project.name", nullable=True)
    motor = _object(
        payload["motor"],
        {"name", "propellant_mass_kg", "total_mass_kg", "diameter_m", "length_m"},
        "$.motor",
    )
    _text(motor["name"], "$.motor.name", nullable=True)
    for key in ("propellant_mass_kg", "total_mass_kg", "diameter_m", "length_m"):
        if motor[key] is not None:
            _number(motor[key], "$.motor." + key, positive=True)
    if (
        motor["propellant_mass_kg"] is not None
        and motor["total_mass_kg"] is not None
        and motor["propellant_mass_kg"] > motor["total_mass_kg"]
    ):
        _fail("MASS", "$.motor.propellant_mass_kg", "Propellant exceeds total motor mass")
    source = _object(
        payload["source"],
        {"source_id", "stream_id", "channel_id", "final_channel_id", "sha256", "file_name", "kind"},
        "$.source",
    )
    for key, value in source.items():
        _text(value, "$.source." + key)
    _hash(source["sha256"], "$.source.sha256")
    if source["kind"] != "experimental":
        _fail("SOURCE_KIND", "$.source.kind", "This format exports experimental primary thrust")
    chain = payload["processing_chain"]
    if not isinstance(chain, list) or not 3 <= len(chain) <= 32:
        _fail("CHAIN", "$.processing_chain", "Expected 3..32 explicit processing stages")
    for index, item in enumerate(chain):
        path = f"$.processing_chain[{index}]"
        _object(
            item,
            {"stage", "id", "version", "api_version", "config", "input", "output", "source_sha256"},
            path,
        )
        for key in ("stage", "id", "version", "api_version", "input", "output"):
            _text(item[key], path + "." + key)
        if not isinstance(item["config"], dict) or item["source_sha256"] != source["sha256"]:
            _fail("CHAIN", path, "Configuration or source identity mismatch")
    calibration = _object(payload["calibration"], {"status", "notes"}, "$.calibration")
    if calibration["status"] not in {"unknown", "estimated", "documented"}:
        _fail("ENUM", "$.calibration.status", "Unsupported qualification")
    _text(calibration["notes"], "$.calibration.notes")
    timing = _object(
        payload["time"],
        {
            "local_to_project_offset_s",
            "ignition_project_s",
            "active_test_project_s",
            "export_time_reference",
        },
        "$.time",
    )
    _number(timing["local_to_project_offset_s"], "$.time.local_to_project_offset_s")
    ignition = _number(timing["ignition_project_s"], "$.time.ignition_project_s")
    active = timing["active_test_project_s"]
    if not isinstance(active, list) or len(active) != 2:
        _fail("LENGTH", "$.time.active_test_project_s", "Expected two endpoints")
    start = _number(active[0], "$.time.active_test_project_s[0]")
    end = _number(active[1], "$.time.active_test_project_s[1]")
    if end <= start or ignition != start or timing["export_time_reference"] != "ignition":
        _fail("TIME", "$.time", "ACTIVE_TEST starts at ignition and has positive duration")
    _object(payload["evidence_curve"], {"time_s", "thrust_n"}, "$.evidence_curve")
    evidence_t, evidence_f = _curve(payload["evidence_curve"], "$.evidence_curve")
    _object(payload["metrics"], {"total_impulse_ns"}, "$.metrics")
    simulation = payload["simulation_curve"]
    if simulation is not None:
        _object(
            simulation,
            {
                "time_s",
                "thrust_n",
                "source_sample_indices",
                "inserted_boundary_indices",
                "interpolation",
                "maximum_gap_s",
            },
            "$.simulation_curve",
        )
        time, force = _curve(simulation, "$.simulation_curve")
        gap = _number(
            simulation["maximum_gap_s"], "$.simulation_curve.maximum_gap_s", positive=True
        )
        if (
            simulation["interpolation"] != "piecewise_linear"
            or time[0] != 0.0
            or not math.isclose(time[-1], end - start, abs_tol=1e-12, rel_tol=1e-12)
        ):
            _fail("POLICY", "$.simulation_curve", "Invalid interval or interpolation policy")
        indices = simulation["source_sample_indices"]
        inserted = simulation["inserted_boundary_indices"]
        if (
            not isinstance(indices, list)
            or len(indices) != len(time)
            or any(type(i) is not int or i < -1 or i >= len(evidence_t) for i in indices)
            or not isinstance(inserted, list)
            or any(type(i) is not int for i in inserted)
            or inserted != [i for i, n in enumerate(indices) if n == -1]
        ):
            _fail("INDICES", "$.simulation_curve", "Sample provenance indices are inconsistent")
        expected_originals = [
            i for i, timestamp in enumerate(evidence_t) if 0 <= timestamp <= end - start
        ]
        if [i for i in indices if i >= 0] != expected_originals:
            _fail("SAMPLE_IDENTITY", "$.simulation_curve", "Original interval samples were omitted")
        for i, (t, f, original) in enumerate(zip(time, force, indices, strict=True)):
            if i and t - time[i - 1] > gap * (1 + 1e-12):
                _fail("GAP", "$.simulation_curve", "Curve exceeds explicit maximum gap")
            if original >= 0:
                if t != evidence_t[original] or f != evidence_f[original]:
                    _fail("SAMPLE_IDENTITY", "$.simulation_curve", "Original sample was modified")
            elif i not in (0, len(time) - 1):
                _fail("INTERPOLATION", "$.simulation_curve", "Only boundaries may be inserted")
            else:
                import bisect

                right = bisect.bisect_right(evidence_t, t)
                if not 0 < right < len(evidence_t):
                    _fail("COVERAGE", "$.simulation_curve", "Boundary outside evidence")
                left = right - 1
                delta = evidence_t[right] - evidence_t[left]
                if delta > gap * (1 + 1e-12):
                    _fail("GAP", "$.simulation_curve", "Boundary spans excessive gap")
                expected = (
                    evidence_f[left]
                    + (evidence_f[right] - evidence_f[left]) * (t - evidence_t[left]) / delta
                )
                if not math.isclose(f, expected, rel_tol=1e-12, abs_tol=1e-12):
                    _fail(
                        "INTERPOLATION", "$.simulation_curve", "Boundary differs from linear policy"
                    )
        impulse = sum(
            (time[i] - time[i - 1]) * (force[i] + force[i - 1]) / 2 for i in range(1, len(time))
        )
        actual = _number(payload["metrics"]["total_impulse_ns"], "$.metrics.total_impulse_ns")
        if not math.isclose(actual, impulse, rel_tol=1e-10, abs_tol=1e-10):
            _fail(
                "IMPULSE",
                "$.metrics.total_impulse_ns",
                "Integral differs from actual-time trapezoids",
            )
    elif payload["metrics"]["total_impulse_ns"] is not None:
        _fail("IMPULSE", "$.metrics.total_impulse_ns", "Unavailable curve requires null impulse")
    if not isinstance(payload["diagnostics"], list) or len(payload["diagnostics"]) > 128:
        _fail("LIMIT", "$.diagnostics", "Expected at most 128 diagnostics")
    for item in payload["diagnostics"]:
        _object(item, {"code", "path", "severity", "message"}, "$.diagnostics[]")
        for key, value in item.items():
            _text(value, "$.diagnostics[]." + key)
        if item["severity"] not in {"warning", "error", "info"}:
            _fail("ENUM", "$.diagnostics[].severity", "Unsupported severity")
    _hash(payload["content_sha256"], "$.content_sha256")
    if MotorPackage_Digest(payload) != payload["content_sha256"]:
        _fail("DIGEST", "$.content_sha256", "Content digest mismatch")
    return payload


def _pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            _fail("DUPLICATE_KEY", "$", f"Duplicate JSON key {key!r}")
        result[key] = value
    return result


def MotorPackage_Load(path: str | Path) -> dict[str, Any]:
    with Path(path).open("rb") as handle:
        data = handle.read(MAX_BYTES + 1)
    if len(data) > MAX_BYTES:
        _fail("LIMIT", "$", "File exceeds 32 MiB")
    try:
        payload = json.loads(
            data.decode("utf-8"),
            object_pairs_hook=_pairs,
            parse_constant=lambda text: _fail("NUMBER", "$", text),
        )
    except (ValueError, UnicodeError, RecursionError) as exc:
        if isinstance(exc, MotorPackageError):
            raise
        raise MotorPackageError("JSON", "$", str(exc)) from exc
    return MotorPackage_Validate(payload)
