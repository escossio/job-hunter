from __future__ import annotations

from .base import BaseSource


class GeekhunterSource(BaseSource):
    name = "geekhunter"

    def collect(self, config):
        # TODO: implementar coleta conservadora em paginas publicas da GeekHunter.
        return []
