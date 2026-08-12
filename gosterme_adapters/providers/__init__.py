"""Provider-owned adapter implementations."""

from .wordwall import GenericWordwallPageAdapter, WordwallDirectAdapter
from .youtube import YouTubeAdapter

__all__ = [
    "GenericWordwallPageAdapter",
    "WordwallDirectAdapter",
    "YouTubeAdapter",
]
