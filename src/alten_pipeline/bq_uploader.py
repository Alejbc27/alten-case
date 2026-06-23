"""Carga idempotente de registros en BigQuery (capa bronze / sandbox).

Implementa la parte 2-2 del pipeline: garantiza la existencia del dataset
``SANDBOX_<app>`` y carga los registros normalizados en la tabla destino con
``WRITE_TRUNCATE`` para que cada corrida sea autocontenida e idempotente.

Diseño:
- ``BigQueryUploader`` se acopla a su cliente mediante una interfaz mínima de
  primitivas (strings y listas), descrita en ``BigQueryClientLike``. Esto
  permite inyectar un fake en los tests sin instalar ``google-cloud-bigquery``.
- En producción se usa ``RealBigQueryClient``, un adaptador delgado sobre la
  librería oficial que traduce esa interfaz de primitivas. Todos los imports
  de la librería son diferidos (lazy) para que el módulo se importe sin ella.
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


class BigQueryUploadError(Exception):
    """Error de dominio para fallos de carga en BigQuery."""


# Interfaz acordada con el cliente inyectado (duck typing, sin ABC formal):
#   get_dataset(dataset_id: str) -> bool
#   create_dataset(dataset_id: str, *, location: str, exists_ok: bool = True) -> None
#   load_table_from_json(rows, *, destination: str, write_disposition: str) -> job
# donde ``job`` expone ``result()`` y ``output_rows``.
# En tests se inyecta un fake con primitivas; en producción se usa el
# adaptador ``RealBigQueryClient`` definido más abajo.


class RealBigQueryClient:
    """Adaptador sobre ``google.cloud.bigquery.Client`` con interfaz de primitivas.

    Importa la librería oficial de forma diferida. De este modo el resto del
    módulo y los tests pueden cargarse sin ``google-cloud-bigquery`` instalada;
    este adaptador solo se usa en producción (cliente inyectado por defecto).
    """

    def __init__(self, project: str) -> None:  # pragma: no cover - requiere GCP
        from google.cloud import bigquery

        self._client = bigquery.Client(project=project)

    def get_dataset(self, dataset_id: str) -> bool:  # pragma: no cover
        from google.cloud.exceptions import NotFound

        try:
            self._client.get_dataset(dataset_id)
            return True
        except NotFound:
            return False

    def create_dataset(
        self, dataset_id: str, *, location: str, exists_ok: bool = True
    ) -> None:  # pragma: no cover
        from google.cloud.bigquery import Dataset

        dataset = Dataset(dataset_id)
        dataset.location = location
        self._client.create_dataset(dataset, exists_ok=exists_ok)

    def load_table_from_json(
        self,
        rows: list[dict],
        *,
        destination: str,
        write_disposition: str = "WRITE_TRUNCATE",
    ) -> Any:  # pragma: no cover
        from google.cloud.bigquery import LoadJobConfig, WriteDisposition

        write_disp = getattr(WriteDisposition, write_disposition, write_disposition)
        job_config = LoadJobConfig(
            write_disposition=write_disp,
            autodetect=True,
        )
        return self._client.load_table_from_json(
            rows, destination=destination, job_config=job_config
        )


class BigQueryUploader:
    """Carga registros normalizados en BigQuery con ``WRITE_TRUNCATE``.

    Parameters
    ----------
    bq_project:
        Proyecto GCP destino. Obligatorio: si está vacío lanza
        ``BigQueryUploadError``.
    bq_dataset:
        Nombre del dataset (default ``SANDBOX_alten_pipeline``).
    bq_table:
        Tabla destino (default ``raw_breweries``).
    bq_location:
        Ubicación geográfica del dataset (default ``US``).
    client:
        Cliente BigQuery inyectable (interfaz ``BigQueryClientLike``). Si es
        ``None`` se construye un ``RealBigQueryClient`` para producción.
    """

    def __init__(
        self,
        *,
        bq_project: str | None,
        bq_dataset: str = "SANDBOX_alten_pipeline",
        bq_table: str = "raw_breweries",
        bq_location: str = "US",
        client: Any | None = None,
    ) -> None:
        if not bq_project:
            raise BigQueryUploadError(
                "bq_project es obligatorio para construir BigQueryUploader"
            )
        self._project = bq_project
        self._dataset = bq_dataset
        self._table = bq_table
        self._location = bq_location
        self._client: Any = (
            client if client is not None else RealBigQueryClient(bq_project)
        )

    @property
    def dataset_id(self) -> str:
        """Identificador completo del dataset (``project.dataset``)."""
        return f"{self._project}.{self._dataset}"

    @property
    def table_id(self) -> str:
        """Identificador completo de la tabla (``project.dataset.table``)."""
        return f"{self._project}.{self._dataset}.{self._table}"

    def ensure_dataset_exists(self) -> None:
        """Crea el dataset si no existe, respetando la ubicación configurada.

        Es idempotente: si el dataset ya existe, no hace nada.

        Raises
        ------
        BigQueryUploadError
            Si el cliente falla al consultar o crear el dataset.
        """
        try:
            exists = self._client.get_dataset(self.dataset_id)
            if exists:
                logger.info("Dataset %s ya existe", self.dataset_id)
                return
            self._client.create_dataset(
                self.dataset_id, location=self._location, exists_ok=True
            )
        except BigQueryUploadError:
            raise
        except Exception as exc:
            raise BigQueryUploadError(
                f"Fallo preparando el dataset {self.dataset_id}: {exc}"
            ) from exc
        logger.info(
            "Dataset %s creado (location=%s)", self.dataset_id, self._location
        )

    def upload(self, rows: list[dict]) -> int:
        """Carga ``rows`` en la tabla destino con ``WRITE_TRUNCATE``.

        Reemplaza por completo el contenido previo: cada corrida es
        autocontenida. Devuelve el número de registros cargados.

        Raises
        ------
        BigQueryUploadError
            Si ``rows`` está vacío o el cliente falla durante la carga.
        """
        if not rows:
            raise BigQueryUploadError(
                "No hay registros para cargar en BigQuery"
            )
        try:
            job = self._client.load_table_from_json(
                rows,
                destination=self.table_id,
                write_disposition="WRITE_TRUNCATE",
            )
            # El cliente real devuelve un job asíncrono; esperamos a que termine.
            if job is not None and hasattr(job, "result"):
                job.result()
        except Exception as exc:
            raise BigQueryUploadError(
                f"Fallo cargando {len(rows)} registros en {self.table_id}: {exc}"
            ) from exc
        logger.info(
            "Cargados %d registros en %s (WRITE_TRUNCATE)",
            len(rows),
            self.table_id,
        )
        return len(rows)
