from __future__ import annotations

from underline_retldc.plugin_api.common import PluginDescriptor, PluginType
from underline_retldc.plugin_api.two_column import TwoColumnRawParserBase


class TrPParser(TwoColumnRawParserBase):
    channel_id = "pressure_raw"
    channel_name = "Raw Chamber Pressure"
    quantity = "pressure"
    semantic_role = "chamber_pressure"
    source_format = "TR_P"
    diagnostic_prefix = "tr_p"

    @property
    def descriptor(self) -> PluginDescriptor:
        return PluginDescriptor(
            plugin_id="builtin.parser.tr_p",
            plugin_type=PluginType.PARSER,
            version="1.0.0",
            api_version="1",
            name="TR_P",
            description="Time / Raw Pressure two-column text parser",
            translation_key="parser.tr_p.name",
        )
