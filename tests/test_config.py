"""Pruebas de `alten_pipeline.config.Settings` (parte2-1: solo descarga API).

Estas pruebas garantizan que la configuración de `parte2-1` se limita a la
descarga desde Open Brewery DB. La configuración de BigQuery (BQ_PROJECT,
BQ_DATASET, etc.) pertenece a `parte2-2` y NO debe aparecer aquí.
"""

from __future__ import annotations

import pytest

from alten_pipeline.config import Settings

# Variables de entorno que `parte2-1` puede leer (solo API de Open Brewery DB).
_API_VARS = (
    "API_BASE_URL",
    "API_PER_PAGE",
    "API_TIMEOUT_SECONDS",
    "API_MAX_RETRIES",
)

# Variables de BigQuery que NO deben existir en parte2-1.
_BQ_VARS = (
    "BQ_PROJECT",
    "BQ_DATASET",
    "BQ_TABLE",
    "BQ_LOCATION",
)


class TestSettingsFromEnv:
    def test_no_requiere_ninguna_variable(self, monkeypatch):
        # Sin ninguna variable de entorno definida, from_env() debe funcionar.
        for var in _API_VARS + _BQ_VARS:
            monkeypatch.delenv(var, raising=False)

        settings = Settings.from_env()

        assert settings is not None

    def test_defaults_aplican_sin_variables(self, monkeypatch):
        for var in _API_VARS + _BQ_VARS:
            monkeypatch.delenv(var, raising=False)

        settings = Settings.from_env()

        assert settings.api_base_url == "https://api.openbrewerydb.org/v1/breweries"
        assert settings.api_per_page == 50
        assert settings.api_timeout_seconds == 30
        assert settings.api_max_retries == 3

    def test_variables_personalizadas_sobrescriben_defaults(self, monkeypatch):
        monkeypatch.setenv("API_BASE_URL", "https://staging.example.test/breweries")
        monkeypatch.setenv("API_PER_PAGE", "100")
        monkeypatch.setenv("API_TIMEOUT_SECONDS", "60")
        monkeypatch.setenv("API_MAX_RETRIES", "5")

        settings = Settings.from_env()

        assert settings.api_base_url == "https://staging.example.test/breweries"
        assert settings.api_per_page == 100
        assert settings.api_timeout_seconds == 60
        assert settings.api_max_retries == 5

    def test_no_contiene_configuracion_bigquery(self, monkeypatch):
        # Guardián de alcance: parte2-1 NO debe exponer configuración BigQuery.
        for var in _BQ_VARS:
            monkeypatch.delenv(var, raising=False)

        settings = Settings.from_env()

        for attr in ("bq_project", "bq_dataset", "bq_table", "bq_location"):
            assert not hasattr(settings, attr), (
                f"Settings.{attr} filtra configuración BigQuery en parte2-1"
            )

    def test_tipo_cast_correcto(self, monkeypatch):
        monkeypatch.setenv("API_PER_PAGE", "200")
        monkeypatch.setenv("API_TIMEOUT_SECONDS", "10.5")

        settings = Settings.from_env()

        assert isinstance(settings.api_per_page, int)
        assert isinstance(settings.api_timeout_seconds, float)
        assert settings.api_per_page == 200
        assert settings.api_timeout_seconds == 10.5
