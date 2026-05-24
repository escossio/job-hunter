from __future__ import annotations

from .base import BaseSource


class ManualUrlsSource(BaseSource):
    name = "manual_urls"

    def collect(self, config):
        # TODO: implementar leitura manual de URLs publicas informadas pelo usuario.
        return []
