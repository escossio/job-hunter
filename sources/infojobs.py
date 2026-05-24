from __future__ import annotations

from .base import BaseSource


class InfojobsSource(BaseSource):
    name = "infojobs"

    def collect(self, config):
        # TODO: implementar apenas modo conservador e parar em bloqueios.
        return []
