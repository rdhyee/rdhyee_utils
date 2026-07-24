"""
Pre-built app bindings for LLM applications and productivity apps.

- Dia: AI browser from The Browser Company (Chromium/ArcCore-based)
- Atlas: ChatGPT's macOS app (Chromium-based, OpenAI)
- Comet: Perplexity's macOS app (Chromium-based)

The DEVONthink adapter lives on the `feat/devonthink-adapter` branch and adds
its own imports here when merged.
"""

from .dia import Dia, DiaWindow, DiaTab
from .atlas import Atlas, AtlasWindow, AtlasTab
from .comet import Comet, CometWindow, CometTab

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
]
