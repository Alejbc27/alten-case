"""Pruebas unitarias de `alten_pipeline.bq_uploader.BigQueryUploader`.

Cubren parte2-2 (carga en BigQuery):
- Creación idempotente del dataset respetando la ubicación configurada.
- Carga con `WRITE_TRUNCATE` (reemplazo total → idempotencia entre corridas).
- Excepción de dominio `BigQueryUploadError` ante proyecto ausente, registros
  vacíos o fallos del cliente.
- Trazabilidad: los registros cargados conservan el `ingestion_run_id` actual.

El cliente BigQuery se inyecta (`FakeBigQueryClient` desde `conftest.py`), por
lo que no se requiere `google-cloud-bigquery` instalada ni credenciales GCP.
"""

from __future__ import annotations

import pytest

from alten_pipeline.bq_uploader import BigQueryUploadError, BigQueryUploader


def make_uploader(client, **overrides):
    """Construye un `BigQueryUploader` con defaults cómodos para tests."""
    defaults = {
        "bq_project": "proyecto-test",
        "bq_dataset": "SANDBOX_alten_pipeline",
        "bq_table": "raw_breweries",
        "bq_location": "US",
        "client": client,
    }
    defaults.update(overrides)
    return BigQueryUploader(**defaults)


def normalized_rows(run_id: str = "run-abc", count: int = 3) -> list[dict]:
    """Genera `count` registros con la trazabilidad de la corrida."""
    return [
        {"id": f"b-{i}", "name": f"Cervecería {i}", "ingestion_run_id": run_id}
        for i in range(count)
    ]


class TestConstructor:
    """Cubre el contrato del constructor."""

    def test_bq_project_obligatorio(self, bq_client):
        with pytest.raises(BigQueryUploadError):
            BigQueryUploader(bq_project="", client=bq_client)

    def test_bq_project_none_lanza_error(self, bq_client):
        with pytest.raises(BigQueryUploadError):
            BigQueryUploader(bq_project=None, client=bq_client)

    def test_destination_compuesto_por_proyecto_dataset_tabla(self, bq_client):
        uploader = make_uploader(
            bq_client,
            bq_project="mi-proyecto",
            bq_dataset="SANDBOX_alten_pipeline",
            bq_table="raw_breweries",
        )

        assert uploader.table_id == "mi-proyecto.SANDBOX_alten_pipeline.raw_breweries"
        assert uploader.dataset_id == "mi-proyecto.SANDBOX_alten_pipeline"


class TestEnsureDatasetExists:
    """Cubre el Requirement: Creación de dataset BigQuery."""

    def test_dataset_no_existente_se_crea_con_location(self, bq_client):
        uploader = make_uploader(bq_client, bq_location="EU")

        uploader.ensure_dataset_exists()

        # El dataset se creó una sola vez con la ubicación configurada.
        assert len(bq_client.create_calls) == 1
        call = bq_client.create_calls[0]
        assert call["dataset_id"] == "proyecto-test.SANDBOX_alten_pipeline"
        assert call["location"] == "EU"
        assert call["exists_ok"] is True

    def test_dataset_ya_existente_no_se_crea(self, bq_client):
        # Preexistencia: el dataset ya está registrado.
        bq_client.datasets["proyecto-test.SANDBOX_alten_pipeline"] = "US"
        uploader = make_uploader(bq_client)

        uploader.ensure_dataset_exists()

        # No se intenta crear de nuevo.
        assert bq_client.create_calls == []

    def test_ensure_es_idempotente_llamada_doble(self, bq_client):
        uploader = make_uploader(bq_client)

        uploader.ensure_dataset_exists()
        uploader.ensure_dataset_exists()

        # La segunda llamada encuentra el dataset ya creado por la primera.
        assert len(bq_client.create_calls) == 1


class TestUpload:
    """Cubre el Requirement: Carga idempotente en BigQuery."""

    def test_carga_todos_los_registros_en_tabla(self, bq_client):
        rows = normalized_rows(run_id="run-1", count=3)
        uploader = make_uploader(bq_client)

        count = uploader.upload(rows)

        assert count == 3
        # La tabla destino recibió los 3 registros.
        loaded = bq_client.loaded[uploader.table_id]
        assert len(loaded) == 3
        assert [r["id"] for r in loaded] == ["b-0", "b-1", "b-2"]

    def test_usa_write_truncate_por_defecto(self, bq_client):
        uploader = make_uploader(bq_client)

        uploader.upload(normalized_rows())

        assert bq_client.last_write_disposition == "WRITE_TRUNCATE"

    def test_segunda_corrida_reemplaza_la_primera(self, bq_client):
        # WRITE_TRUNCATE => el contenido previo se descarta.
        uploader = make_uploader(bq_client)
        uploader.upload(normalized_rows(run_id="run-vieja", count=5))

        # La tabla ya tiene 5 registros de la corrida vieja.
        assert len(bq_client.loaded[uploader.table_id]) == 5

        uploader.upload(normalized_rows(run_id="run-nueva", count=2))

        # Tras la nueva corrida SOLO quedan los 2 registros nuevos.
        loaded = bq_client.loaded[uploader.table_id]
        assert len(loaded) == 2
        assert all(r["ingestion_run_id"] == "run-nueva" for r in loaded)
        # No quedan registros de la corrida vieja (idempotencia entre corridas).
        assert all(r["ingestion_run_id"] != "run-vieja" for r in loaded)

    def test_registros_vacios_lanza_error_de_dominio(self, bq_client):
        uploader = make_uploader(bq_client)

        with pytest.raises(BigQueryUploadError):
            uploader.upload([])

    def test_fallo_del_cliente_se_envuelve_en_error_de_dominio(self, bq_client):
        bq_client.load_exception = RuntimeError("simulated GCP failure")
        uploader = make_uploader(bq_client)

        with pytest.raises(BigQueryUploadError, match="raw_breweries"):
            uploader.upload(normalized_rows())

    def test_llama_result_del_job_para_esperar_la_carga(self, bq_client):
        # Los load jobs de BigQuery son asíncronos: el uploader DEBE llamar
        # `job.result()` para bloquear hasta terminar. Este test protege esa
        # llamada: si se elimina del uploader, `result_called` queda en False.
        uploader = make_uploader(bq_client)

        uploader.upload(normalized_rows(count=2))

        last_job = bq_client.last_job
        assert last_job is not None
        assert last_job.result_called is True, (
            "upload() debe llamar job.result() para esperar la carga asíncrona"
        )
        last_call = bq_client.load_calls[-1]
        assert last_call["destination"] == uploader.table_id
        assert len(last_call["rows"]) == 2

    def test_no_llamar_result_en_carga_fallida_no_marca_job(self, bq_client):
        # Si la carga falla antes de devolver el job, no hay result() que
        # llamar; el error se envuelve en BigQueryUploadError.
        bq_client.load_exception = RuntimeError("fallo previo al job")
        uploader = make_uploader(bq_client)

        with pytest.raises(BigQueryUploadError):
            uploader.upload(normalized_rows())

        # No se llegó a crear ningún job (la excepción se lanza antes).
        assert bq_client.last_job is None


class TestEnsureDatasetErrors:
    """Cubre fallos durante la preparación del dataset (Warning de revisión).

    Por coherencia con `upload()`, los fallos del cliente durante
    `ensure_dataset_exists()` se envuelven en `BigQueryUploadError`.
    """

    def test_fallo_en_get_dataset_se_envuelve_en_error_de_dominio(self, bq_client):
        bq_client.get_dataset_exception = RuntimeError("permiso denegado")
        uploader = make_uploader(bq_client)

        with pytest.raises(BigQueryUploadError, match="dataset"):
            uploader.ensure_dataset_exists()

    def test_fallo_en_create_dataset_se_envuelve_en_error_de_dominio(self, bq_client):
        bq_client.create_dataset_exception = RuntimeError("cuota excedida")
        uploader = make_uploader(bq_client)

        with pytest.raises(BigQueryUploadError, match="dataset"):
            uploader.ensure_dataset_exists()

    def test_fallo_en_create_dataset_no_deja_dataset_a_medias(self, bq_client):
        # Si create_dataset falla, el dataset no debe quedar registrado como
        # existente en el fake (refleja que la creación no completó).
        bq_client.create_dataset_exception = RuntimeError("cuota excedida")
        uploader = make_uploader(bq_client)

        with pytest.raises(BigQueryUploadError):
            uploader.ensure_dataset_exists()

        assert uploader.dataset_id not in bq_client.datasets
