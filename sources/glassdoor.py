from __future__ import annotations

from .base import BaseSource


class GlassdoorSource(BaseSource):
    name = "glassdoor"

    def collect(self, config):
        # TODO: implementar somente coleta publica, parando em login/captcha/bloqueio.
        return []
