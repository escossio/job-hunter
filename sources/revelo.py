from __future__ import annotations

from .base import BaseSource


class ReveloSource(BaseSource):
    name = "revelo"

    def collect(self, config):
        # TODO: implementar apenas modo manual ou paginas publicas permitidas.
        return []
