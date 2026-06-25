"""Shared application container passed to every handler module.

Bundles the long-lived, stateful services so handlers don't reach for globals.
"""

from __future__ import annotations

from dataclasses import dataclass

from bot.config import Settings
from bot.services.batch import BatchStore
from bot.services.openrouter import OpenRouterClient
from bot.services.ratelimit import RateLimiter


@dataclass
class AppContext:
    settings: Settings
    store: BatchStore
    limiter: RateLimiter
    orclient: OpenRouterClient
