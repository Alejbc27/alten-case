"""Pruebas unitarias de `alten_pipeline.api_client.BreweryClient`.

Se cubre parte2-1 (descarga desde API):
- Normalización de registros (mapeo, nulos, trazabilidad).
- Paginación real hasta página vacía.
- Reintentos ante 5xx/429 y timeout.
- Agotamiento de reintentos lanza `ApiClientError`.

La sesión HTTP es inyectable: los tests usan dobles de `requests.Session`
(`FakeSession`) para no realizar llamadas de red reales ni requerir
`requests-mock` como dependencia adicional.
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path

import pytest
import requests

from alten_pipeline.api_client import ApiClientError, BreweryClient

FIXTURES = Path(__file__).parent / "fixtures"


def load_fixture(name: str) -> list[dict]:
    """Carga un fixture JSON desde `tests/fixtures`."""
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


class FakeResponse:
    """Doble minimalista de `requests.Response`."""

    def __init__(self, payload: list[dict], status_code: int = 200) -> None:
        self._payload = payload
        self.status_code = status_code

    def json(self) -> list[dict]:
        return self._payload

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise requests.exceptions.HTTPError(
                f"{self.status_code} Server Error"
            )


class FakeSession:
    """Doble de `requests.Session` que sirve respuestas por orden de llamada.

    Registra cada llamada a `get()` en `self.calls` como un dict con ``url``,
    ``params`` y ``timeout`` para poder asertar sobre paginación y reintentos.
    """

    def __init__(self, responses: list[FakeResponse | Exception]) -> None:
        # Cola de respuestas: cada elemento es un FakeResponse o una excepción
        # que se lanzará al invocar `get` (para simular fallos transitorios).
        self._responses = list(responses)
        self.calls: list[dict] = []

    def get(
        self, url: str, params: dict | None = None, timeout: float | None = None, **kwargs
    ) -> FakeResponse:
        self.calls.append({"url": url, "params": dict(params or {}), "timeout": timeout})
        item = self._responses.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


# ---------------------------------------------------------------------------
# Normalización
# ---------------------------------------------------------------------------


class TestNormalize:
    """Cubre el Requirement: Normalización de registros."""

    def test_registro_completo_mapea_todos_los_campos(self) -> None:
        run_id = "11111111-1111-1111-1111-111111111111"
        record = load_fixture("breweries_page1.json")[0]

        normalized = BreweryClient._normalize(record, run_id)

        assert normalized["id"] == record["id"]
        assert normalized["name"] == "MadTree Brewing 2.0"
        assert normalized["brewery_type"] == "regional"
        assert normalized["street"] == "3301 Madison Rd"
        assert normalized["city"] == "Cincinnati"
        assert normalized["state"] == "Ohio"
        assert normalized["country"] == "United States"
        assert normalized["postal_code"] == "45209"
        assert normalized["phone"] == "5138368646"
        assert normalized["website_url"] == "https://www.madtreebrewing.com"
        # Coordenadas casteadas a float.
        assert normalized["longitude"] == pytest.approx(-84.4084379)
        assert normalized["latitude"] == pytest.approx(39.1073494)

    def test_campos_de_trazabilidad(self) -> None:
        run_id = "22222222-2222-2222-2222-222222222222"
        record = load_fixture("breweries_page1.json")[0]
        before = datetime.now(timezone.utc)

        normalized = BreweryClient._normalize(record, run_id)

        after = datetime.now(timezone.utc)
        # ingestion_run_id es el UUID de la corrida recibido.
        assert normalized["ingestion_run_id"] == run_id
        # ingestion_ts es timezone-aware en UTC y reciente.
        ts: datetime = normalized["ingestion_ts"]
        assert ts.tzinfo == timezone.utc
        assert before <= ts <= after
        # source_payload contiene el JSON crudo original.
        assert normalized["source_payload"] == json.dumps(record)

    def test_campos_nulos_se_preservan_como_none(self) -> None:
        run_id = "33333333-3333-3333-3333-333333333333"
        record = load_fixture("breweries_page2_last.json")[0]

        normalized = BreweryClient._normalize(record, run_id)

        assert normalized["street"] is None
        assert normalized["phone"] is None
        assert normalized["website_url"] is None
        # No se descarta el registro: sigue teniendo id.
        assert normalized["id"] == record["id"]

    def test_run_id_es_uuid_v4_valido_por_defecto(self) -> None:
        client = BreweryClient(base_url="https://example.test")

        parsed = uuid.UUID(client.run_id)

        assert parsed.version == 4


# ---------------------------------------------------------------------------
# fetch_page: HTTP + reintentos
# ---------------------------------------------------------------------------


class TestFetchPage:
    """Cubre los Requirements: Descarga paginada y Reintentos/timeouts."""

    def test_retorna_registros_de_una_pagina(self) -> None:
        page1 = load_fixture("breweries_page1.json")
        session = FakeSession([FakeResponse(page1)])
        client = BreweryClient(
            base_url="https://example.test/breweries", per_page=50, session=session
        )

        result = client.fetch_page(page=1)

        assert result == page1
        assert len(result) == 3

    def test_envia_parametros_page_per_page_y_timeout(self) -> None:
        page1 = load_fixture("breweries_page1.json")
        session = FakeSession([FakeResponse(page1)])
        client = BreweryClient(
            base_url="https://example.test/breweries",
            per_page=50,
            timeout=42,
            session=session,
        )

        client.fetch_page(page=7)

        assert len(session.calls) == 1
        call = session.calls[0]
        assert call["url"] == "https://example.test/breweries"
        assert call["params"] == {"page": 7, "per_page": 50}
        assert call["timeout"] == 42

    def test_reintenta_y_recupera_tras_error_500(self) -> None:
        page1 = load_fixture("breweries_page1.json")
        session = FakeSession([FakeResponse([], 500), FakeResponse(page1, 200)])
        client = BreweryClient(
            base_url="https://example.test/breweries", max_retries=3, session=session
        )

        result = client.fetch_page(page=1)

        assert result == page1
        # Primer intento falló (500), segundo exitoso.
        assert len(session.calls) == 2

    def test_reintenta_tras_429(self) -> None:
        page1 = load_fixture("breweries_page1.json")
        session = FakeSession([FakeResponse([], 429), FakeResponse(page1, 200)])
        client = BreweryClient(
            base_url="https://example.test/breweries", max_retries=3, session=session
        )

        result = client.fetch_page(page=1)

        assert result == page1

    def test_error_404_no_se_reintenta(self) -> None:
        session = FakeSession([FakeResponse([], 404)])
        client = BreweryClient(
            base_url="https://example.test/breweries", max_retries=3, session=session
        )

        with pytest.raises(ApiClientError):
            client.fetch_page(page=1)

        # Los errores 4xx no transitorios no deben reintentarse.
        assert len(session.calls) == 1

    def test_agota_reintentos_lanza_api_client_error(self) -> None:
        session = FakeSession([FakeResponse([], 500), FakeResponse([], 500)])
        client = BreweryClient(
            base_url="https://example.test/breweries", max_retries=2, session=session
        )

        with pytest.raises(ApiClientError):
            client.fetch_page(page=1)

        # Se realizaron exactamente los intentos configurados.
        assert len(session.calls) == 2

    def test_timeout_recuperable_cuenta_como_intento(self) -> None:
        page1 = load_fixture("breweries_page1.json")
        session = FakeSession(
            [requests.exceptions.Timeout("timeout"), FakeResponse(page1, 200)]
        )
        client = BreweryClient(
            base_url="https://example.test/breweries", max_retries=3, session=session
        )

        result = client.fetch_page(page=1)

        assert result == page1

    def test_timeout_agotado_lanza_api_client_error(self) -> None:
        session = FakeSession(
            [requests.exceptions.Timeout("timeout"), requests.exceptions.Timeout("timeout")]
        )
        client = BreweryClient(
            base_url="https://example.test/breweries", max_retries=2, session=session
        )

        with pytest.raises(ApiClientError):
            client.fetch_page(page=1)


# ---------------------------------------------------------------------------
# fetch_all: paginación + normalización integradas
# ---------------------------------------------------------------------------


class TestFetchAll:
    """Cubre el Requirement: Descarga paginada de API (paginación completa)."""

    def test_recopila_todas_las_paginas_hasta_vacia(self) -> None:
        page1 = load_fixture("breweries_page1.json")
        page2 = load_fixture("breweries_page2_last.json")
        session = FakeSession(
            [FakeResponse(page1), FakeResponse(page2), FakeResponse([])]
        )
        client = BreweryClient(
            base_url="https://example.test/breweries", per_page=2, session=session
        )

        records = client.fetch_all()

        # 3 registros de page1 + 1 de page2 = 4 normalizados.
        assert len(records) == 4
        # Tres llamadas: páginas 1, 2 y 3 (vacía detiene el bucle).
        assert [c["params"]["page"] for c in session.calls] == [1, 2, 3]

    def test_normaliza_con_run_id_compartido_y_trazabilidad(self) -> None:
        page1 = load_fixture("breweries_page1.json")
        session = FakeSession([FakeResponse(page1), FakeResponse([])])
        client = BreweryClient(
            base_url="https://example.test/breweries",
            run_id="44444444-4444-4444-4444-444444444444",
            session=session,
        )

        records = client.fetch_all()

        assert all(r["ingestion_run_id"] == client.run_id for r in records)
        assert all("ingestion_ts" in r for r in records)
        assert all("source_payload" in r for r in records)
        # El primer registro normalizado conserva el id crudo del fixture.
        assert records[0]["id"] == page1[0]["id"]

    def test_se_detiene_ante_primera_pagina_vacia(self) -> None:
        session = FakeSession([FakeResponse([])])
        client = BreweryClient(
            base_url="https://example.test/breweries", session=session
        )

        records = client.fetch_all()

        assert records == []
        assert len(session.calls) == 1


# ---------------------------------------------------------------------------
# fetch_all con límite de registros (API_MAX_RECORDS)
# ---------------------------------------------------------------------------


class TestFetchAllMaxRecords:
    """Cubre el límite configurable de registros en la descarga.

    El límite detiene la descarga (no descarga todo para truncar después), de
    forma que la ejecución normal de la prueba no consuma toda la API.
    """

    def test_max_records_negativo_es_invalido(self) -> None:
        with pytest.raises(ValueError, match="max_records"):
            BreweryClient(base_url="https://example.test/breweries", max_records=-1)

    def test_limite_detiene_descarga_sin_pedir_paginas_extra(self) -> None:
        # max_records=2 con página de 2 registros: alcanza el límite en la
        # primera página y NO pide la siguiente.
        page = load_fixture("breweries_page1.json")[:2]
        # Se ofrecen 3 páginas (la última vacía); solo debe consumirse la 1ª.
        # Sin el corte, el bucle terminaría en la página vacía tras 3 llamadas,
        # y la aserción len(calls)==1 fallaría de forma clara.
        session = FakeSession([FakeResponse(page), FakeResponse(page), FakeResponse([])])
        client = BreweryClient(
            base_url="https://example.test/breweries",
            per_page=2,
            max_records=2,
            session=session,
        )

        records = client.fetch_all()

        assert len(records) == 2
        assert len(session.calls) == 1

    def test_limite_trunca_cuando_una_pagina_supera_el_limite(self) -> None:
        # max_records=3 con una sola página de 4 registros: trunca a 3 y no
        # pide más páginas.
        page = load_fixture("breweries_page1.json")  # 3 registros
        big_page = page + [{"id": "extra-1", "name": "Extra", "brewery_type": "micro"}]
        session = FakeSession(
            [FakeResponse(big_page), FakeResponse(big_page), FakeResponse([])]
        )
        client = BreweryClient(
            base_url="https://example.test/breweries",
            per_page=4,
            max_records=3,
            session=session,
        )

        records = client.fetch_all()

        assert len(records) == 3
        assert len(session.calls) == 1

    def test_limite_none_descarga_todo_hasta_pagina_vacia(self) -> None:
        # max_records=None → comportamiento original (sin límite).
        page = load_fixture("breweries_page1.json")
        session = FakeSession([FakeResponse(page), FakeResponse([])])
        client = BreweryClient(
            base_url="https://example.test/breweries",
            max_records=None,
            session=session,
        )

        records = client.fetch_all()

        assert len(records) == len(page)
        assert [c["params"]["page"] for c in session.calls] == [1, 2]

    def test_limite_cero_es_equivalente_a_none(self) -> None:
        # 0 se trata como "sin límite" (descargar todo).
        page = load_fixture("breweries_page1.json")
        session = FakeSession([FakeResponse(page), FakeResponse([])])
        client = BreweryClient(
            base_url="https://example.test/breweries",
            max_records=0,
            session=session,
        )

        records = client.fetch_all()

        assert len(records) == len(page)
