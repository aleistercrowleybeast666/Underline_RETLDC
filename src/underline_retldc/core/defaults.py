from __future__ import annotations

from dataclasses import dataclass

from underline_retldc.core.units import DEFAULT_DISPLAY_UNITS


@dataclass(frozen=True, slots=True)
class FactoryDefaults:
    theme: str = "light"
    locale: str = "zh_CN"
    parser_auto_probe: bool = True
    parser_auto_select_threshold: float = 0.90
    parser_auto_select_margin: float = 0.10
    tabular_auto_mapping: bool = True
    tabular_auto_prefill: bool = True
    new_channel_calibration_id: str = "builtin.calibration.identity"
    missing_unit_policy: str = "canonical_si_by_quantity"
    unit_display_mode: str = "engineering"
    segmentation_reference: str = "auto"
    segmentation_auto_priority: tuple[str, ...] = ("chamber_pressure", "thrust")
    missing_pre_baseline: str = "assume_zero"
    missing_post_baseline: str = "assume_zero"
    after_import_workspace: str = "project"


FACTORY_DEFAULTS = FactoryDefaults()
FACTORY_DISPLAY_UNITS = dict(DEFAULT_DISPLAY_UNITS)
