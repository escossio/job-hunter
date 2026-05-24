from __future__ import annotations

from .base import BaseSource


class IndeedSource(BaseSource):
    name = "indeed"

    def collect(self, config):
        # TODO: implementar apenas modo conservador e parar em bloqueios.
        return []
