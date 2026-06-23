"""Paquete de la pipeline de datos para la prueba técnica de Alten.

Expone los componentes públicos del pipeline de ingesta Open Brewery DB →
BigQuery: configuración, cliente de descarga y cargador de BigQuery.

El entrypoint de orquestación (`main`/`run`) vive en el submódulo
`alten_pipeline.main` y NO se importa aquí a propósito: importarlo desde el
``__init__`` precargaría el submódulo en ``sys.modules`` al importar el paquete,
lo que provoca un ``RuntimeWarning`` de runpy al ejecutar
``python -m alten_pipeline.main``. Se invoca siempre vía submódulo.
"""

from __future__ import annotations

from .api_client import ApiClientError, BreweryClient
from .bq_uploader import BigQueryUploadError, BigQueryUploader
from .config import Settings

__all__ = [
    "ApiClientError",
    "BigQueryUploadError",
    "BigQueryUploader",
    "BreweryClient",
    "Settings",
]

__version__ = "0.1.0"
