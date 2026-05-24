from __future__ import annotations

from .base import BaseSource


class TramposSource(BaseSource):
    name = "trampos"

    def collect(self, config):
        # TODO: implementar coleta conservadora em paginas publicas da Trampos.
        return []
