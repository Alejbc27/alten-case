"""Paquete de la pipeline de datos para la prueba técnica de Alten.

Expone los componentes públicos del pipeline de ingesta Open Brewery DB →
BigQuery: configuración, cliente de descarga, cargador de BigQuery y el
entrypoint de orquestación.
"""

from __future__ import annotations

from .api_client import ApiClientError, BreweryClient
from .bq_uploader import BigQueryUploadError, BigQueryUploader
from .config import Settings
from .main import main, run

__all__ = [
    "ApiClientError",
    "BigQueryUploadError",
    "BigQueryUploader",
    "BreweryClient",
    "Settings",
    "main",
    "run",
]

__version__ = "0.1.0"
