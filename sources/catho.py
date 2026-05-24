from __future__ import annotations

from .base import BaseSource


class CathoSource(BaseSource):
    name = "catho"

    def collect(self, config):
        # TODO: implementar somente coleta publica, sem login.
        return []
