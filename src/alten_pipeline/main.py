"""Entrypoint de orquestación: descarga API → carga BigQuery.

Conecta `BreweryClient` (parte 2-1) y `BigQueryUploader` (parte 2-2) en una
corrida con trazabilidad: un mismo `run_id` recorre la descarga y se registra
en cada fila cargada. Emite logs de inicio y fin con el recuento de registros.

`run()` admite inyectar ambas dependencias para tests end-to-end sin red ni
GCP. `main()` es el punto de entrada CLI: lee `Settings` del entorno y delega
en `run()`.
"""

from __future__ import annotations

import logging
import sys
from typing import Any

from .api_client import BreweryClient
from .bq_uploader import BigQueryUploadError, BigQueryUploader
from .config import Settings

logger = logging.getLogger("alten_pipeline")


def run(
    settings: Settings,
    *,
    brewery_client: Any | None = None,
    uploader: Any | None = None,
) -> int:
    """Ejecuta la corrida: descarga → asegura dataset → carga en BigQuery.

    Orden intencional: la descarga ocurre antes de construir/validar el
    uploader. Así una fuente vacía (API sin registros) es un no-op válido que
    no requiere ``BQ_PROJECT`` ni BigQuery: se loguea y se devuelve 0. Solo si
    hay registros se exige ``BQ_PROJECT`` (cuando el uploader no se inyecta).

    Parameters
    ----------
    settings:
        Configuración del pipeline.
    brewery_client:
        Cliente de descarga inyectable. Si es ``None`` se construye uno real a
        partir de ``settings``.
    uploader:
        Cargador BigQuery inyectable. Si es ``None`` se construye uno real
        cuando haya registros que cargar; en ese caso ``settings.bq_project``
        es obligatorio.

    Returns
    -------
    int
        Número de registros cargados.

    Raises
    ------
    BigQueryUploadError
        Si hay registros que cargar, no se inyecta uploader y
        ``BQ_PROJECT`` no está definido.
    """
    if brewery_client is None:
        brewery_client = BreweryClient(
            base_url=settings.api_base_url,
            per_page=settings.api_per_page,
            timeout=settings.api_timeout_seconds,
            max_retries=settings.api_max_retries,
        )

    run_id = getattr(brewery_client, "run_id", "desconocido")
    logger.info("Inicia corrida: %s", run_id)

    records = brewery_client.fetch_all()

    # Fuente vacía: no-op válido. No se construye ni se llama al uploader (que
    # lanzaría BigQueryUploadError con lista vacía), así que BQ_PROJECT tampoco
    # es necesario. Se registra el motivo y se devuelve 0.
    if not records:
        logger.warning(
            "Corrida %s: no hay registros para cargar; se omite BigQuery", run_id
        )
        logger.info("Finaliza corrida: %s — 0 registros cargados", run_id)
        return 0

    # Hay registros: ahora sí se necesita BigQuery. Construimos/validamos el
    # uploader aquí (no antes) para no bloquear el no-op de fuente vacía.
    if uploader is None:
        if not settings.bq_project:
            raise BigQueryUploadError(
                "BQ_PROJECT es obligatorio para ejecutar el pipeline contra BigQuery"
            )
        uploader = BigQueryUploader(
            bq_project=settings.bq_project,
            bq_dataset=settings.bq_dataset,
            bq_table=settings.bq_table,
            bq_location=settings.bq_location,
        )

    uploader.ensure_dataset_exists()
    count = uploader.upload(records)

    logger.info("Finaliza corrida: %s — %d registros cargados", run_id, count)
    return count


def main(argv: list[str] | None = None) -> int:
    """Punto de entrada CLI: lee configuración y ejecuta la corrida."""
    settings = Settings.from_env()
    logging.basicConfig(
        level=getattr(logging, settings.log_level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s — %(message)s",
    )
    try:
        run(settings)
    except BigQueryUploadError as exc:
        logger.error("Corrida abortada: %s", exc)
        return 1
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
