from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any


class DiagnosticSeverity(StrEnum):
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"


@dataclass(frozen=True, slots=True)
class Diagnostic:
    severity: DiagnosticSeverity
    code: str
    message: str
    source: str | None = None
    line: int | None = None
    plugin_id: str | None = None
    details: Mapping[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "severity": self.severity.value,
            "code": self.code,
            "message": self.message,
        }
        if self.source is not None:
            payload["source"] = self.source
        if self.line is not None:
            payload["line"] = self.line
        if self.plugin_id is not None:
            payload["plugin_id"] = self.plugin_id
        if self.details:
            payload["details"] = dict(self.details)
        return payload

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> Diagnostic:
        return cls(
            severity=DiagnosticSeverity(str(payload["severity"])),
            code=str(payload["code"]),
            message=str(payload["message"]),
            source=str(payload["source"]) if payload.get("source") is not None else None,
            line=int(payload["line"]) if payload.get("line") is not None else None,
            plugin_id=(
                str(payload["plugin_id"]) if payload.get("plugin_id") is not None else None
            ),
            details=dict(payload.get("details", {})),
        )

