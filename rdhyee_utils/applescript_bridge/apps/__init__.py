"""
Pre-built app bindings for LLM applications and productivity apps.

- Dia: OpenAI's macOS LLM app (browser)
- Atlas: ChatGPT's macOS app (Chromium-based)
- Comet: Perplexity's macOS app (Chromium-based)
- DEVONthink: DEVONthink 4 document/knowledge manager
"""

from .dia import Dia, DiaWindow, DiaTab
from .atlas import Atlas, AtlasWindow, AtlasTab
from .comet import Comet, CometWindow, CometTab
from .devonthink import DEVONthink, DTDatabase, DTRecord

__all__ = [
    "Dia",
    "DiaWindow",
    "DiaTab",
    "Atlas",
    "AtlasWindow",
    "AtlasTab",
    "Comet",
    "CometWindow",
    "CometTab",
    "DEVONthink",
    "DTDatabase",
    "DTRecord",
]
