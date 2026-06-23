"""Configuración del pipeline de ingesta Open Brewery DB → BigQuery.

Toda la configuración se lee desde variables de entorno con valores por defecto
razonables, por lo que ``Settings.from_env()`` funciona sin definir ninguna
variable.

Salvo ``BQ_PROJECT``, ninguna variable es obligatoria para construir
``Settings``. ``BQ_PROJECT`` se devuelve como ``None`` si no está definida y su
carácter obligatorio se valida en el entrypoint (`main`): así la parte 2-1
(descarga API) sigue funcionando sin configurar BigQuery.
"""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    """Configuración del pipeline de ingesta Open Brewery DB → BigQuery."""

    # --- Descarga API (parte 2-1) ---
    api_base_url: str = "https://api.openbrewerydb.org/v1/breweries"
    api_per_page: int = 50
    api_timeout_seconds: float = 30
    api_max_retries: int = 3
    # Límite de registros a descargar. Por defecto 100 para no consumir toda
    # la API en la ejecución normal de la prueba. ``None`` (o 0 en la variable
    # de entorno) significa descargar todo. Los valores negativos son inválidos.
    api_max_records: int | None = 100

    # --- Carga BigQuery (parte 2-2) ---
    # ``bq_project`` es obligatorio para ejecutar contra BigQuery, pero se deja
    # como ``None`` cuando la variable no está definida para no romper la
    # construcción en contextos API-only. La validación se hace en `main`.
    bq_project: str | None = None
    bq_dataset: str = "SANDBOX_alten_pipeline"
    bq_table: str = "raw_breweries"
    bq_location: str = "US"
    log_level: str = "INFO"

    @classmethod
    def from_env(cls) -> Settings:
        """Construye ``Settings`` desde variables de entorno.

        Ninguna variable es obligatoria aquí: todos los campos tienen valor
        por defecto. ``BQ_PROJECT`` ausente se traduce a ``bq_project=None``;
        ``main`` decide si eso es un error según el contexto de ejecución.
        """
        return cls(
            api_base_url=os.environ.get(
                "API_BASE_URL", "https://api.openbrewerydb.org/v1/breweries"
            ),
            api_per_page=int(os.environ.get("API_PER_PAGE", "50")),
            api_timeout_seconds=float(os.environ.get("API_TIMEOUT_SECONDS", "30")),
            api_max_retries=int(os.environ.get("API_MAX_RETRIES", "3")),
            api_max_records=_parse_max_records(os.environ.get("API_MAX_RECORDS")),
            bq_project=os.environ.get("BQ_PROJECT") or None,
            bq_dataset=os.environ.get("BQ_DATASET", "SANDBOX_alten_pipeline"),
            bq_table=os.environ.get("BQ_TABLE", "raw_breweries"),
            bq_location=os.environ.get("BQ_LOCATION", "US"),
            log_level=os.environ.get("LOG_LEVEL", "INFO"),
        )


def _parse_max_records(raw: str | None) -> int | None:
    """Interpreta ``API_MAX_RECORDS``.

    - Ausente o vacío → 100 (default razonable para la prueba).
    - ``0`` → ``None`` (descargar todo).
    - Entero positivo → ese valor.
    - Entero negativo → error de configuración.
    """
    if not raw:
        return 100
    parsed = int(raw)
    if parsed < 0:
        raise ValueError("API_MAX_RECORDS no puede ser negativo")
    return parsed or None
