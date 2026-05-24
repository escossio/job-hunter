from __future__ import annotations

from .base import BaseSource


class LinkedinSource(BaseSource):
    name = "linkedin"

    def collect(self, config):
        # TODO: implementar somente fluxo manual, sem login automatico e sem candidatura.
        return []
