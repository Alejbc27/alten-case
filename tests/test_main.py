"""Pruebas del entrypoint de orquestación `alten_pipeline.main`.

Cubren parte2-2 (conexión BreweryClient → BigQueryUploader):
- Orquestación end-to-end con dobles (sin red ni GCP).
- Logs de inicio y fin de corrida con el `run_id`.
- Validación de `BQ_PROJECT` obligatorio cuando no se inyectan dependencias.
- Retorno del número de registros cargados.

`run()` acepta dependencias inyectables (`brewery_client`, `uploader`) para
que los tests no requieran `requests` en red ni `google-cloud-bigquery`.
"""

from __future__ import annotations

import logging
from types import SimpleNamespace

import pytest

from alten_pipeline.bq_uploader import BigQueryUploadError
from alten_pipeline.config import Settings
from alten_pipeline.main import run


def make_settings(**overrides) -> Settings:
    """Settings con valores por defecto (BQ_PROJECT presente)."""
    defaults = {
        "api_base_url": "https://example.test/breweries",
        "bq_project": "proyecto-test",
    }
    defaults.update(overrides)
    return Settings(**defaults)


class FakeBreweryClient:
    """Doble de `BreweryClient` con `fetch_all` y `run_id`."""

    def __init__(self, records: list[dict], run_id: str = "run-fake-123") -> None:
        self._records = records
        self.run_id = run_id
        self.fetch_all_called = False

    def fetch_all(self) -> list[dict]:
        self.fetch_all_called = True
        return list(self._records)


class FakeUploader:
    """Doble de `BigQueryUploader` con `ensure_dataset_exists` y `upload`."""

    def __init__(self) -> None:
        self.ensure_called = False
        self.upload_called = False
        self.uploaded_rows: list[dict] = []
        self.upload_exception: Exception | None = None

    def ensure_dataset_exists(self) -> None:
        self.ensure_called = True

    def upload(self, rows: list[dict]) -> int:
        self.upload_called = True
        self.uploaded_rows = list(rows)
        if self.upload_exception is not None:
            raise self.upload_exception
        return len(rows)


@pytest.fixture
def cap_logs(caplog):
    """Captura logs en nivel INFO del logger del paquete."""
    caplog.set_level(logging.INFO, logger="alten_pipeline")
    return caplog


class TestRun:
    def test_orquesta_descarga_asegura_dataset_y_carga(self, bq_client):
        records = [{"id": "b1"}, {"id": "b2"}]
        brewery = FakeBreweryClient(records, run_id="run-xyz")
        uploader = FakeUploader()

        count = run(make_settings(), brewery_client=brewery, uploader=uploader)

        assert count == 2
        assert brewery.fetch_all_called is True
        assert uploader.ensure_called is True
        assert uploader.uploaded_rows == records

    def test_registra_logs_de_inicio_y_fin_con_run_id(self, cap_logs):
        records = [{"id": "b1"}]
        brewery = FakeBreweryClient(records, run_id="run-abc-999")
        uploader = FakeUploader()

        run(make_settings(), brewery_client=brewery, uploader=uploader)

        mensajes = [r.getMessage() for r in cap_logs.records]
        assert any("Inicia corrida: run-abc-999" in m for m in mensajes)
        assert any(
            "Finaliza corrida: run-abc-999 — 1 registros cargados" in m
            for m in mensajes
        )

    def test_bq_project_ausente_lanza_error_si_hay_registros_y_no_hay_uploader(
        self, cap_logs
    ):
        # Con registros que cargar y sin uploader inyectado, BQ_PROJECT es
        # obligatorio: la corrida debe fallar de forma clara. Usamos API con
        # datos (no vacía) porque el error solo aplica cuando hay algo que cargar.
        settings = make_settings(bq_project=None)
        brewery = FakeBreweryClient([{"id": "b1"}], run_id="run-no-bq")

        with pytest.raises(BigQueryUploadError, match="BQ_PROJECT"):
            run(settings, brewery_client=brewery)

    def test_api_vacia_con_bq_project_none_retorna_cero_sin_construir_uploader(
        self, cap_logs
    ):
        # Camino real (sin uploader inyectado): API vacía + BQ_PROJECT ausente
        # → no-op válido. El contrato dice que la fuente vacía NO requiere
        # BigQuery, así que run() devuelve 0 SIN validar/construir el uploader.
        # Antes del reordenamiento esto lanzaba BigQueryUploadError porque la
        # validación ocurría antes de fetch_all().
        settings = make_settings(bq_project=None)
        brewery = FakeBreweryClient([], run_id="run-empty-no-bq")

        count = run(settings, brewery_client=brewery)

        assert count == 0
        mensajes = [r.getMessage() for r in cap_logs.records]
        assert any("no hay registros" in m.lower() for m in mensajes)

    def test_no_construye_uploader_real_si_se_inyecta(self, bq_client):
        # Con uploader inyectado, BQ_PROJECT puede faltar (modo test / API-only).
        settings = make_settings(bq_project=None)
        brewery = FakeBreweryClient([{"id": "b1"}], run_id="run-injected")
        uploader = FakeUploader()

        count = run(settings, brewery_client=brewery, uploader=uploader)

        assert count == 1
        assert uploader.upload_called is True

    def test_propaga_fallo_de_carga(self, cap_logs):
        brewery = FakeBreweryClient([{"id": "b1"}], run_id="run-fail")
        uploader = FakeUploader()
        uploader.upload_exception = BigQueryUploadError("fallo simulado")

        with pytest.raises(BigQueryUploadError, match="fallo simulado"):
            run(make_settings(), brewery_client=brewery, uploader=uploader)

    def test_api_vacia_no_invoca_bigquery_y_devuelve_cero(self, cap_logs):
        # Contrato: si la API no devuelve registros, la corrida se considera
        # un no-op válido (fuente vacía). NO se llama al uploader (evitar el
        # BigQueryUploadError que el uploader real lanza con listas vacías),
        # se registra un aviso y se devuelve 0.
        brewery = FakeBreweryClient([], run_id="run-empty")
        uploader = FakeUploader()

        count = run(make_settings(), brewery_client=brewery, uploader=uploader)

        assert count == 0
        # No se toca BigQuery en absoluto.
        assert uploader.ensure_called is False
        assert uploader.upload_called is False
        # Se registra el motivo del no-op para trazabilidad.
        mensajes = [r.getMessage() for r in cap_logs.records]
        assert any("no hay registros" in m.lower() or "sin datos" in m.lower() for m in mensajes), (
            "La corrida vacía debe loguear que no hay datos"
        )


class TestMainCargaDotenv:
    """Cubre la carga automática de `.env` en el entrypoint CLI (`main`).

    `main()` invoca `load_dotenv(override=False)` ANTES de `Settings.from_env()`
    para que las variables del archivo `.env` estén disponibles, sin sobrescribir
    las variables de entorno reales (que mantienen prioridad).

    Nota: necesitamos el *módulo* `alten_pipeline.main` (no la función `main`)
    para hacer `monkeypatch.setattr` sobre `load_dotenv`/`run`/`Settings`. Lo
    obtenemos vía `sys.modules["alten_pipeline.main"]`, poblado al importar la
    función con `from alten_pipeline.main import main`.
    """

    @staticmethod
    def _main_module():
        import sys

        return sys.modules["alten_pipeline.main"]

    def test_main_invoca_load_dotenv(self, monkeypatch):
        from alten_pipeline.main import main as main_fn

        main_mod = self._main_module()
        llamado = {"dotenv": False}

        def fake_load_dotenv(*args, **kwargs):
            llamado["dotenv"] = True
            return True

        monkeypatch.setattr(main_mod, "load_dotenv", fake_load_dotenv)
        monkeypatch.setattr(main_mod, "run", lambda settings: 0)

        rc = main_fn()

        assert llamado["dotenv"] is True
        assert rc == 0

    def test_main_usa_override_false_para_preservar_entorno_real(self, monkeypatch):
        from alten_pipeline.main import main as main_fn

        main_mod = self._main_module()
        capturado: dict = {}

        def fake_load_dotenv(*args, **kwargs):
            capturado.update(kwargs)
            return True

        monkeypatch.setattr(main_mod, "load_dotenv", fake_load_dotenv)
        monkeypatch.setattr(main_mod, "run", lambda settings: 0)

        main_fn()

        # override=False => las variables de entorno reales NO se sobrescriben
        # con las del archivo .env; el entorno del proceso manda.
        assert capturado.get("override") is False

    def test_main_llama_load_dotenv_antes_que_settings_from_env(self, monkeypatch):
        from alten_pipeline.main import main as main_fn

        main_mod = self._main_module()
        orden: list[str] = []
        monkeypatch.setattr(
            main_mod, "load_dotenv", lambda *a, **k: orden.append("dotenv") or True
        )
        monkeypatch.setattr(
            main_mod.Settings,
            "from_env",
            lambda: orden.append("settings") or Settings(),
        )
        monkeypatch.setattr(main_mod, "run", lambda settings: 0)

        main_fn()

        assert orden == ["dotenv", "settings"]

    def test_main_es_seguro_si_no_hay_archivo_env(self, monkeypatch):
        # load_dotenv() retorna False (y no lanza) cuando no encuentra .env.
        # main() debe continuar con normalidad usando solo el entorno real.
        from alten_pipeline.main import main as main_fn

        main_mod = self._main_module()
        monkeypatch.setattr(main_mod, "load_dotenv", lambda *a, **k: False)
        monkeypatch.setattr(main_mod, "run", lambda settings: 0)

        rc = main_fn()

        assert rc == 0
