"""Configuración de la descarga desde la API de Open Brewery DB.

Parte 2-1: esta configuración se limita a la descarga. La configuración de
BigQuery (proyecto, dataset, tabla, ubicación) se introduce en la parte 2-2
y NO debe aparecer aquí.

Toda la configuración de API tiene valores por defecto razonables, por lo que
``Settings.from_env()`` funciona sin definir ninguna variable de entorno.
"""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    """Configuración de descarga desde Open Brewery DB."""

    api_base_url: str = "https://api.openbrewerydb.org/v1/breweries"
    api_per_page: int = 50
    api_timeout_seconds: float = 30
    api_max_retries: int = 3

    @classmethod
    def from_env(cls) -> "Settings":
        """Construye ``Settings`` desde variables de entorno.

        Ninguna variable es obligatoria: todos los campos tienen valor por
        defecto, por lo que la descarga funciona sin configuración adicional.
        """
        return cls(
            api_base_url=os.environ.get(
                "API_BASE_URL", "https://api.openbrewerydb.org/v1/breweries"
            ),
            api_per_page=int(os.environ.get("API_PER_PAGE", "50")),
            api_timeout_seconds=float(os.environ.get("API_TIMEOUT_SECONDS", "30")),
            api_max_retries=int(os.environ.get("API_MAX_RETRIES", "3")),
        )
