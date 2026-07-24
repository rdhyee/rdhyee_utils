"""
Pre-built app bindings for LLM applications and productivity apps.

- Dia: AI browser from The Browser Company (Chromium/ArcCore-based)
- Atlas: ChatGPT's macOS app (Chromium-based, OpenAI)
- Comet: Perplexity's macOS app (Chromium-based)
- DEVONthink: DEVONthink 4 document/knowledge manager
"""

from .dia import Dia, DiaWindow, DiaTab, DiaJavaScriptDisabled
from .atlas import Atlas, AtlasWindow, AtlasTab
from .comet import Comet, CometWindow, CometTab
from .devonthink import DEVONthink, DTDatabase, DTRecord

__all__ = [
    "Dia",
    "DiaWindow",
    "DiaTab",
    "DiaJavaScriptDisabled",
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
