"""Cliente de descarga desde la API de Open Brewery DB.

Implementa la parte 2-1 del pipeline: descarga paginada, normalización de
registros y reintentos ante fallos transitorios.

La sesión HTTP (`requests.Session`) es inyectable para permitir pruebas sin
llamadas de red reales ni dependencias de mock adicionales.
"""

from __future__ import annotations

import json
import logging
import uuid
from datetime import UTC, datetime
from typing import Any

import requests

logger = logging.getLogger(__name__)


class ApiClientError(Exception):
    """Error de dominio para fallos no recuperables del cliente de API."""


class BreweryClient:
    """Descarga y normaliza cervecerías desde Open Brewery DB.

    Parameters
    ----------
    base_url:
        URL base del endpoint de breweries.
    per_page:
        Registros solicitados por página (máximo 200 en la API).
    timeout:
        Timeout HTTP por solicitud, en segundos.
    max_retries:
        Reintentos ante errores transitorios (5xx, 429, timeout de red).
    max_records:
        Número máximo de registros a descargar. ``None`` o ``0`` significan
        descargar todo. Si se alcanza el límite, la descarga se detiene
        (truncando la última página si la excede).
    run_id:
        Identificador UUID de la corrida. Si se omite, se genera uno nuevo.
    session:
        Sesión ``requests`` inyectable. Si se omite, se crea una nueva.
    """

    #: Estados HTTP considerados transitorios y por tanto reintentables.
    RETRY_STATUS = (429, 500, 502, 503, 504)

    def __init__(
        self,
        base_url: str,
        *,
        per_page: int = 50,
        timeout: float = 30,
        max_retries: int = 3,
        max_records: int | None = None,
        run_id: str | None = None,
        session: requests.Session | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.per_page = per_page
        self.timeout = timeout
        self.max_retries = max_retries
        if max_records is not None and max_records < 0:
            raise ValueError("max_records no puede ser negativo")
        # ``0`` se normaliza a ``None`` (descargar todo de forma explícita).
        self.max_records = max_records or None
        self.run_id = run_id or str(uuid.uuid4())
        self._session = session or requests.Session()

    def fetch_page(self, page: int) -> list[dict[str, Any]]:
        """Descarga una única página de breweries (registro crudo del API).

        Aplica reintentos ante fallos transitorios (5xx, 429, timeout de red)
        hasta ``max_retries`` intentos; los agota lanzando ``ApiClientError``.
        """
        return self._request(params={"page": page, "per_page": self.per_page})

    def fetch_all(self) -> list[dict[str, Any]]:
        """Descarga todas las breweries paginando hasta recibir una página vacía.

        Cada registro crudo se normaliza con ``self.run_id`` para trazabilidad.
        La paginación es incremental (``page = 1, 2, 3, ...``) y se detiene en
        la primera respuesta vacía, que marca el fin de los resultados.

        Si ``max_records`` está configurado, la descarga se detiene al alcanzar
        ese número de registros (truncando la última página si la excede), de
        forma que la ejecución normal no consuma toda la API.
        """
        normalized: list[dict[str, Any]] = []
        page = 1
        while True:
            raw_page = self.fetch_page(page=page)
            if not raw_page:
                break
            normalized.extend(
                self._normalize(record, self.run_id) for record in raw_page
            )
            if self.max_records is not None and len(normalized) >= self.max_records:
                return normalized[: self.max_records]
            page += 1
        return normalized

    def _request(self, params: dict[str, Any]) -> list[dict[str, Any]]:
        """Ejecuta un GET con reintentos sobre la URL base.

        - Errores de red (timeout, conexión) y estados en ``RETRY_STATUS`` se
          reintentan hasta ``max_retries`` intentos.
        - Otros errores 4xx no se reintentan: fallan de inmediato.
        - Al agotarse los intentos se lanza ``ApiClientError`` con contexto.
        """
        last_failure: str | Exception = "sin intentos"
        for attempt in range(1, self.max_retries + 1):
            try:
                response = self._session.get(
                    self.base_url, params=params, timeout=self.timeout
                )
            except requests.RequestException as exc:
                last_failure = exc
                logger.warning(
                    "Intento %d/%d falló (%s) para %s",
                    attempt,
                    self.max_retries,
                    exc,
                    self.base_url,
                )
                continue

            if response.status_code in self.RETRY_STATUS:
                last_failure = f"HTTP {response.status_code}"
                logger.warning(
                    "Intento %d/%d: estado %d reintentable para %s",
                    attempt,
                    self.max_retries,
                    response.status_code,
                    self.base_url,
                )
                continue

            if response.status_code >= 400:
                # Error cliente no reintentable: falla inmediata.
                raise ApiClientError(
                    f"HTTP {response.status_code} para {self.base_url}"
                )

            return response.json()

        raise ApiClientError(
            f"Agotados {self.max_retries} intentos para {self.base_url}: "
            f"último fallo={last_failure}"
        )

    @staticmethod
    def _normalize(record: dict[str, Any], run_id: str) -> dict[str, Any]:
        """Aplana un registro crudo del API a las columnas de ``raw_breweries``.

        Los campos nulos se preservan como ``None``. Las coordenadas se
        castean a ``float`` y el payload original se conserva en
        ``source_payload`` como cadena JSON. ``ingestion_ts`` se emite como
        string ISO 8601 (timezone-aware UTC) para que la fila completa sea
        serializable a JSON — BigQuery infiere TIMESTAMP desde el string ISO.
        """
        return {
            "id": record.get("id"),
            "name": record.get("name"),
            "brewery_type": record.get("brewery_type"),
            "street": record.get("street"),
            "city": record.get("city"),
            "state": record.get("state"),
            "country": record.get("country"),
            "postal_code": record.get("postal_code"),
            "phone": record.get("phone"),
            "website_url": record.get("website_url"),
            "longitude": _to_float(record.get("longitude")),
            "latitude": _to_float(record.get("latitude")),
            "ingestion_ts": datetime.now(UTC).isoformat(),
            "ingestion_run_id": run_id,
            "source_payload": json.dumps(record),
        }


def _to_float(value: Any) -> float | None:
    """Castea a ``float`` preservando ``None``; devuelve ``None`` si no procede."""
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
