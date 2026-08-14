from __future__ import annotations

from underline_retldc.plugin_api.common import (
    PluginDescriptor,
    PluginType,
)
from underline_retldc.plugin_api.two_column import TwoColumnRawParserBase


class TrFParser(TwoColumnRawParserBase):
    channel_id = "thrust_raw"
    channel_name = "Raw Thrust"
    quantity = "force"
    semantic_role = "thrust"
    source_format = "TR_F"
    diagnostic_prefix = "tr_f"

    @property
    def descriptor(self) -> PluginDescriptor:
        return PluginDescriptor(
            plugin_id="builtin.parser.tr_f",
            plugin_type=PluginType.PARSER,
            version="1.0.0",
            api_version="1",
            name="TR_F",
            description="Time / Raw Force two-column text parser",
            translation_key="parser.tr_f.name",
        )
