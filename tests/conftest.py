"""Fixtures compartidas para el conjunto de pruebas.

Expone `FakeBigQueryClient`, un doble que implementa la misma interfaz de
primitivas que `BigQueryUploader` espera de su cliente inyectado: ni este
doble ni los tests que lo usan requieren `google-cloud-bigquery` instalada ni
credenciales GCP.

La interfaz acordada (duck typing) es:

    get_dataset(dataset_id: str) -> bool
    create_dataset(dataset_id: str, *, location: str, exists_ok: bool = True) -> None
    load_table_from_json(rows, *, destination: str, write_disposition: str) -> JobLike

`JobLike` expone `result()` (bloquea hasta "terminar") y `output_rows`
(numero de filas cargadas, opcional).
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest


class FakeBigQueryJob:
    """Doble del job de carga de BigQuery."""

    def __init__(self, output_rows: int = 0) -> None:
        self._output_rows = output_rows
        self.result_called = False

    def result(self) -> "FakeBigQueryJob":
        self.result_called = True
        return self

    @property
    def output_rows(self) -> int:
        return self._output_rows


class FakeBigQueryClient:
    """Doble del cliente BigQuery basado en primitivas (strings y dicts).

    Mantiene estado en memoria:
    - ``datasets``: mapping ``dataset_id -> location`` de datasets existentes.
    - ``loaded``: mapping ``destination -> list[rows]`` con la última carga
      (``WRITE_TRUNCATE`` se modela como reemplazo del contenido previo).
    - ``last_write_disposition``: último modo de escritura recibido.
    """

    def __init__(self) -> None:
        self.datasets: dict[str, str] = {}
        self.loaded: dict[str, list[dict]] = {}
        self.last_write_disposition: str | None = None
        self.create_calls: list[dict[str, Any]] = []
        self.load_calls: list[dict[str, Any]] = []
        # Último job devuelto por `load_table_from_json`. Permite a los tests
        # afirmar que el uploader llamó `job.result()` (carga asíncrona).
        self.last_job: FakeBigQueryJob | None = None
        # Si se define, el método correspondiente lanza esta excepción.
        self.load_exception: Exception | None = None
        self.get_dataset_exception: Exception | None = None
        self.create_dataset_exception: Exception | None = None

    # --- API de consulta/creación de datasets ---

    def get_dataset(self, dataset_id: str) -> bool:
        if self.get_dataset_exception is not None:
            raise self.get_dataset_exception
        return dataset_id in self.datasets

    def create_dataset(
        self, dataset_id: str, *, location: str, exists_ok: bool = True
    ) -> None:
        if self.create_dataset_exception is not None:
            raise self.create_dataset_exception
        self.datasets[dataset_id] = location
        self.create_calls.append(
            {"dataset_id": dataset_id, "location": location, "exists_ok": exists_ok}
        )

    # --- API de carga ---

    def load_table_from_json(
        self,
        rows: list[dict],
        *,
        destination: str,
        write_disposition: str = "WRITE_TRUNCATE",
    ) -> FakeBigQueryJob:
        self.last_write_disposition = write_disposition
        self.load_calls.append(
            {
                "rows": list(rows),
                "destination": destination,
                "write_disposition": write_disposition,
            }
        )
        if self.load_exception is not None:
            raise self.load_exception
        # WRITE_TRUNCATE reemplaza; cualquier otro modo se trata como append
        # para que los tests puedan diferenciar si lo necesitan.
        if write_disposition == "WRITE_TRUNCATE":
            self.loaded[destination] = list(rows)
        else:
            self.loaded.setdefault(destination, []).extend(rows)
        job = FakeBigQueryJob(output_rows=len(rows))
        self.last_job = job
        return job


@pytest.fixture
def bq_client() -> FakeBigQueryClient:
    """Cliente BigQuery fake para tests de `BigQueryUploader` y `main`."""
    return FakeBigQueryClient()


@pytest.fixture
def sample_rows() -> list[dict]:
    """Registros normalizados de ejemplo (salida de `BreweryClient`)."""
    return [
        SimpleNamespace(
            **{
                "id": "b1",
                "name": "Cervecería Uno",
                "brewery_type": "micro",
                "ingestion_run_id": "run-1",
                "ingestion_ts": "2026-01-01T00:00:00Z",
            }
        ).__dict__
        for _ in range(3)
    ]
