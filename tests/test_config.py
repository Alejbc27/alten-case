"""Pruebas de `alten_pipeline.config.Settings`.

Cubren:
- parte2-1: configuración de descarga desde Open Brewery DB (API).
- parte2-2: configuración de carga en BigQuery (proyecto, dataset, tabla,
  ubicación, nivel de log).

`BQ_PROJECT` es obligatoria para ejecutar el pipeline contra BigQuery, pero
`Settings.from_env()` no falla si está ausente: la devuelve como ``None`` y la
validación de obligatoriedad se realiza en el entrypoint (`main`). Así los
tests de la parte 2-1 (solo API) siguen funcionando sin definir BigQuery.
"""

from __future__ import annotations

import pytest

from alten_pipeline.config import Settings

# Variables de entorno de API (Open Brewery DB).
_API_VARS = (
    "API_BASE_URL",
    "API_PER_PAGE",
    "API_TIMEOUT_SECONDS",
    "API_MAX_RETRIES",
    "API_MAX_RECORDS",
)

# Variables de BigQuery.
_BQ_VARS = (
    "BQ_PROJECT",
    "BQ_DATASET",
    "BQ_TABLE",
    "BQ_LOCATION",
    "LOG_LEVEL",
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

    def test_tipo_cast_correcto(self, monkeypatch):
        monkeypatch.setenv("API_PER_PAGE", "200")
        monkeypatch.setenv("API_TIMEOUT_SECONDS", "10.5")

        settings = Settings.from_env()

        assert isinstance(settings.api_per_page, int)
        assert isinstance(settings.api_timeout_seconds, float)
        assert settings.api_per_page == 200
        assert settings.api_timeout_seconds == 10.5


class TestSettingsBigQuery:
    """Configuración BigQuery introducida en parte2-2."""

    def test_bq_project_es_none_por_defecto(self, monkeypatch):
        # BQ_PROJECT ausente → None. La obligatoriedad se valida en main().
        for var in _BQ_VARS:
            monkeypatch.delenv(var, raising=False)

        settings = Settings.from_env()

        assert settings.bq_project is None

    def test_defaults_bigquery_aplican(self, monkeypatch):
        for var in _BQ_VARS:
            monkeypatch.delenv(var, raising=False)

        settings = Settings.from_env()

        assert settings.bq_dataset == "SANDBOX_alten_pipeline"
        assert settings.bq_table == "raw_breweries"
        assert settings.bq_location == "US"
        assert settings.log_level == "INFO"

    def test_bq_project_se_lee_de_entorno(self, monkeypatch):
        monkeypatch.setenv("BQ_PROJECT", "mi-proyecto-gcp")

        settings = Settings.from_env()

        assert settings.bq_project == "mi-proyecto-gcp"

    def test_variables_bigquery_personalizadas_sobrescriben_defaults(self, monkeypatch):
        monkeypatch.setenv("BQ_PROJECT", "proyecto-test")
        monkeypatch.setenv("BQ_DATASET", "SANDBOX_otro")
        monkeypatch.setenv("BQ_TABLE", "raw_otra")
        monkeypatch.setenv("BQ_LOCATION", "EU")
        monkeypatch.setenv("LOG_LEVEL", "DEBUG")

        settings = Settings.from_env()

        assert settings.bq_project == "proyecto-test"
        assert settings.bq_dataset == "SANDBOX_otro"
        assert settings.bq_table == "raw_otra"
        assert settings.bq_location == "EU"
        assert settings.log_level == "DEBUG"

    def test_log_level_se_mantiene_como_string(self, monkeypatch):
        monkeypatch.setenv("LOG_LEVEL", "WARNING")

        settings = Settings.from_env()

        assert settings.log_level == "WARNING"
        assert isinstance(settings.log_level, str)


class TestSettingsMaxRecords:
    """Límite configurable de registros a descargar (ajuste de enunciado)."""

    def test_default_es_100_cuando_ausente(self, monkeypatch):
        # Por defecto, la descarga se limita a 100 registros para no consumir
        # toda la API en la ejecución normal de la prueba.
        for var in _API_VARS:
            monkeypatch.delenv(var, raising=False)

        settings = Settings.from_env()

        assert settings.api_max_records == 100

    def test_cero_significa_descargar_todo(self, monkeypatch):
        # API_MAX_RECORDS=0 desactiva el límite (descarga completa).
        monkeypatch.setenv("API_MAX_RECORDS", "0")

        settings = Settings.from_env()

        assert settings.api_max_records is None

    def test_valor_personalizado_se_aplica(self, monkeypatch):
        monkeypatch.setenv("API_MAX_RECORDS", "200")

        settings = Settings.from_env()

        assert settings.api_max_records == 200

    def test_vacio_cae_en_default(self, monkeypatch):
        # Variable definida pero vacía → default (100), consistente con el
        # tratamiento de otras variables opcionales.
        monkeypatch.setenv("API_MAX_RECORDS", "")

        settings = Settings.from_env()

        assert settings.api_max_records == 100

    def test_valor_negativo_es_invalido(self, monkeypatch):
        monkeypatch.setenv("API_MAX_RECORDS", "-1")

        with pytest.raises(ValueError, match="API_MAX_RECORDS"):
            Settings.from_env()

    def test_valor_no_numerico_es_invalido(self, monkeypatch):
        monkeypatch.setenv("API_MAX_RECORDS", "abc")

        with pytest.raises(ValueError):
            Settings.from_env()
