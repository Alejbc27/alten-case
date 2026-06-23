"""Validación estructural de `sql/transform.sql` (parte2-3).

Estos tests NO ejecutan SQL contra BigQuery (no hay motor SQL embebido en el
repo). Verifican que el archivo de producción exista y contenga los tokens
contractuales derivados del spec y el design de `sql-transform-idempotente`:

- una única sentencia `CREATE OR REPLACE TABLE`
- lectura desde `SANDBOX_alten_pipeline.raw_breweries`
- escritura en `INTEGRATION.integration_prueba_tecnica`
- `brewery_id` extraído vía `JSON_VALUE(source_payload, '$.id')`
- deduplicación por `brewery_id` con `ROW_NUMBER() ... PARTITION BY brewery_id`
- tres CTEs con responsabilidad única
- `CURRENT_DATE() AS transformation_date`
- sin `MERGE`, sin shell scripting
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

SQL_PATH = Path(__file__).resolve().parent.parent / "sql" / "transform.sql"


@pytest.fixture(scope="module")
def transform_sql() -> str:
    """Contenido íntegro de `sql/transform.sql` (archivo de producción)."""
    if not SQL_PATH.is_file():
        pytest.fail(f"No existe el archivo de producción: {SQL_PATH}")
    return SQL_PATH.read_text(encoding="utf-8")


def _strip_comments(sql: str) -> str:
    """Elimina comentarios `-- ...` de línea para contar sentencias reales."""
    return re.sub(r"--.*$", "", sql, flags=re.MULTILINE)


def test_archivo_existe_y_no_esta_vacio(transform_sql: str) -> None:
    # Prueba que el archivo de producción existe y tiene contenido real.
    assert transform_sql.strip(), "sql/transform.sql está vacío"


def test_una_sola_sentencia_create_or_replace(transform_sql: str) -> None:
    # El spec exige exactamente una sentencia top-level (CREATE OR REPLACE TABLE).
    sin_comentarios = _strip_comments(transform_sql)
    # Aceptamos 0 o 1 punto y coma final, pero no múltiples sentencias.
    puntos_y_coma = sin_comentarios.count(";")
    assert puntos_y_coma <= 1, (
        f"Se esperaba una única sentencia; se hallaron {puntos_y_coma} ';'"
    )
    assert "CREATE OR REPLACE TABLE" in sin_comentarios.upper()


def test_no_hay_shell_ni_scripting(transform_sql: str) -> None:
    # El spec prohíbe wrappers de shell o llamadas a gcloud/bq dentro del SQL.
    texto = transform_sql.lower()
    for prohibido in ("#!/bin", "gcloud", "bq query", "bash"):
        assert prohibido not in texto, f"Encontrado token de scripting: {prohibido!r}"


def test_no_usa_merge(transform_sql: str) -> None:
    # El design eligió CREATE OR REPLACE sobre MERGE por simplicidad/idempotencia.
    assert "merge" not in transform_sql.lower(), "No debe usarse MERGE"


def test_destino_y_fuente_correctos(transform_sql: str) -> None:
    # Tablas fuente y destino del contrato.
    assert "integration_prueba_tecnica" in transform_sql
    assert "raw_breweries" in transform_sql
    assert "SANDBOX_alten_pipeline" in transform_sql
    assert "INTEGRATION" in transform_sql


def test_brewery_id_desde_json_value(transform_sql: str) -> None:
    # brewery_id se obtiene del payload JSON, no de una columna plana `id`.
    assert "JSON_VALUE(source_payload, '$.id')" in transform_sql


def test_deduplicacion_por_brewery_id(transform_sql: str) -> None:
    # Dedup por brewery_id con tiebreaker ingestion_ts DESC, ingestion_run_id DESC.
    assert "ROW_NUMBER()" in transform_sql
    assert "PARTITION BY brewery_id" in transform_sql
    assert "ORDER BY ingestion_ts DESC" in transform_sql
    assert "ingestion_run_id DESC" in transform_sql
    assert "rn = 1" in transform_sql or "rn=1" in transform_sql


def test_tres_ctes_con_responsabilidad_unica(transform_sql: str) -> None:
    # El usuario exige tres CTEs legibles con estos nombres.
    for cte in (
        "source_breweries",
        "ranked_breweries",
        "deduplicated_breweries",
    ):
        assert cte in transform_sql, f"Falta la CTE {cte!r}"


def test_transformation_date_con_current_date(transform_sql: str) -> None:
    # El design decidió CURRENT_DATE() AS transformation_date (sobre TIMESTAMP).
    assert "CURRENT_DATE()" in transform_sql
    assert "transformation_date" in transform_sql


def test_columnas_finales_presentes(transform_sql: str) -> None:
    # Columnas mínimas del contrato de salida del design.
    for columna in (
        "brewery_id",
        "name",
        "brewery_type",
        "city",
        "state",
        "country",
        "phone",
        "website_url",
        "ingestion_ts",
        "transformation_date",
    ):
        assert columna in transform_sql, f"Falta la columna final {columna!r}"
