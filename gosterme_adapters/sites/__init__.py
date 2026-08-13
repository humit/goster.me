"""Site-owned adapter implementations."""

from .ilkokul_akademi import (
    IlkokulAkademiGithubEmbedAdapter,
    IlkokulAkademiNativeAdapter,
)
from .ilk_okul import IlkOkulNativeAdapter
from .testsaati import TestSaatiZombifyAdapter

__all__ = [
    "IlkokulAkademiGithubEmbedAdapter",
    "IlkokulAkademiNativeAdapter",
    "IlkOkulNativeAdapter",
    "TestSaatiZombifyAdapter",
]
