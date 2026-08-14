from __future__ import annotations

from underline_retldc.plugin_api.common import PluginDescriptor, PluginType
from underline_retldc.plugin_api.two_column import TwoColumnRawParserBase


class TrTParser(TwoColumnRawParserBase):
    channel_id = "temperature_raw"
    channel_name = "Raw Temperature"
    quantity = "temperature"
    semantic_role = "temperature"
    source_format = "TR_T"
    diagnostic_prefix = "tr_t"

    @property
    def descriptor(self) -> PluginDescriptor:
        return PluginDescriptor(
            plugin_id="builtin.parser.tr_t",
            plugin_type=PluginType.PARSER,
            version="1.0.0",
            api_version="1",
            name="TR_T",
            description="Time / Raw Temperature two-column text parser",
            translation_key="parser.tr_t.name",
        )
