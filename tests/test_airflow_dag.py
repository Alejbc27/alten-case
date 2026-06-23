"""Validación del DAG de Airflow `test` y del entorno Docker Compose (parte 3).

Estrategia en dos capas, alineada con `tests/test_transform_sql.py`:

1. **Tests estáticos (siempre se ejecutan, sin Airflow instalado)**: verifican
   que los archivos de producción existen y contienen los tokens contractuales
   derivados del spec/design de `airflow-dag-test` (``dag_id``, schedule cron,
   ``default_args`` exactos, ``TimeDiff``, comentario Hook vs Connection,
   servicios del compose, montaje de ``dags/`` y ausencia de secretos GCP).

2. **Tests de importación/gráfico (opcionales)**: protegidos con
   ``pytest.importorskip('airflow')``. Se ejecutan solo si Airflow está
   disponible (p. ej. dentro del contenedor del compose) y validan la carga del
   DAG en el ``DagBag``, los task_ids, el orden topológico y el operador
   ``TimeDiff.execute()``. Localmente (sin Airflow) se omiten sin error.
"""

from __future__ import annotations

import logging
import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
DAG_PATH = REPO_ROOT / "dags" / "test.py"
COMPOSE_PATH = REPO_ROOT / "docker-compose.yml"
DOCS_HOOKS_PATH = REPO_ROOT / "docs" / "airflow-hooks-vs-connections.md"


# ------------------------------------------------------------------
# Fixtures de lectura de archivos de producción
# ------------------------------------------------------------------


@pytest.fixture(scope="module")
def dag_source() -> str:
    """Contenido íntegro de ``dags/test.py`` (archivo de producción)."""
    if not DAG_PATH.is_file():
        pytest.fail(f"No existe el archivo del DAG: {DAG_PATH}")
    return DAG_PATH.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def compose_source() -> str:
    """Contenido íntegro de ``docker-compose.yml`` (archivo de producción)."""
    if not COMPOSE_PATH.is_file():
        pytest.fail(f"No existe el archivo compose: {COMPOSE_PATH}")
    return COMPOSE_PATH.read_text(encoding="utf-8")


# ------------------------------------------------------------------
# Tests estáticos: docker-compose.yml
# ------------------------------------------------------------------


def test_compose_existe_y_no_esta_vacio(compose_source: str) -> None:
    # El compose es el entregable mínimo de infraestructura local.
    assert compose_source.strip(), "docker-compose.yml está vacío"


def test_compose_define_webserver_y_scheduler(compose_source: str) -> None:
    # El spec exige explícitamente ambos servicios visibles.
    assert "webserver" in compose_source, "Falta el servicio 'webserver'"
    assert "scheduler" in compose_source, "Falta el servicio 'scheduler'"


def test_compose_expone_puerto_8080(compose_source: str) -> None:
    # La Web UI de Airflow debe quedar accesible en http://localhost:8080.
    assert "8080:8080" in compose_source, "El puerto 8080 no está expuesto"


def test_compose_monta_directorio_dags(compose_source: str) -> None:
    # El DAG local debe estar visible dentro del contenedor.
    assert "/opt/airflow/dags" in compose_source, "No se monta el dir de DAGs"
    assert "./dags" in compose_source, "No se monta ./dags desde el host"


def test_compose_deshabilita_ejemplos(compose_source: str) -> None:
    # Evitamos cargar los DAGs de ejemplo y ensuciar la UI de prueba.
    assert "LOAD_EXAMPLES" in compose_source
    assert re.search(r"LOAD_EXAMPLES.*false", compose_source, re.IGNORECASE)


def test_compose_no_requiere_credenciales_gcp(compose_source: str) -> None:
    # Entorno local aislado: sin secretos reales ni dependencias de GCP.
    # Se buscan tokens de *configuración* de credenciales (env vars, claves),
    # no la palabra suelta en un comentario aclaratorio.
    texto = compose_source.lower()
    prohibidos = (
        "google_application_credentials",  # env var de credencial SA
        "service-account",  # montaje de clave de servicio
        "service_account",
        "gcloud",  # invocación a la CLI de GCP
        "/google/",  # montaje típico de config gcloud
    )
    for prohibido in prohibidos:
        assert prohibido not in texto, f"Encontrada referencia GCP/secreto: {prohibido!r}"


# ------------------------------------------------------------------
# Tests estáticos: dags/test.py
# ------------------------------------------------------------------


def test_dag_existe_y_no_esta_vacio(dag_source: str) -> None:
    # El DAG es el entregable central de la parte 3.
    assert dag_source.strip(), "dags/test.py está vacío"


def test_dag_id_es_test(dag_source: str) -> None:
    # El enunciado fija el identificador del DAG.
    assert 'dag_id="test"' in dag_source or "dag_id='test'" in dag_source


def test_dag_schedule_diario_03_utc(dag_source: str) -> None:
    # Schedule diario a las 03:00 UTC (cron estándar de 5 campos).
    assert "0 3 * * *" in dag_source, "No se halló el cron diario 03:00 UTC"


def test_dag_catchup_false(dag_source: str) -> None:
    # Imprescindible con start_date=1900: evita un backfill masivo al arrancar.
    assert "catchup" in dag_source and "False" in dag_source


def test_dag_default_args_exactos(dag_source: str) -> None:
    # El enunciado fija los default_args; el spec exige coincidencia exacta.
    # Se normalizan las comillas para no acoplarse al estilo de formato (ruff).
    src = dag_source.replace("'", '"')
    for token in (
        '"owner": "airflow"',
        '"depends_on_past": False',
        "datetime(1900, 1, 1)",
        '"retries": 1',
        "timedelta(seconds=5)",
    ):
        assert token in src, f"Falta el token de default_args: {token!r}"


def test_dag_define_time_diff_operator(dag_source: str) -> None:
    # TimeDiff extiende BaseOperator y recibe el parámetro diff_date.
    assert "class TimeDiff(BaseOperator)" in dag_source, "Falta la clase TimeDiff"
    assert "diff_date" in dag_source, "TimeDiff debe aceptar diff_date"


def test_dag_contiene_comentario_hook_vs_connection(dag_source: str) -> None:
    # El enunciado pide un comentario sobre Hook vs Connection. En el DAG queda
    # un comentario breve; la explicación detallada vive en el doc (ver test de
    # doc). Aquí validamos que el comentario mencione ambos conceptos y enlace.
    texto = dag_source.lower()
    assert "hook" in texto, "Falta mención de 'Hook' en el comentario"
    assert "connection" in texto, "Falta mención de 'Connection' en el comentario"
    assert "airflow-hooks-vs-connections" in texto, (
        "El comentario debe enlazar al doc de explicación"
    )


def test_doc_hooks_vs_connections_existe_y_explica() -> None:
    # El detalle de Hook vs Connection vive en un doc repo-visible y escaneable.
    if not DOCS_HOOKS_PATH.is_file():
        pytest.fail(f"No existe el doc: {DOCS_HOOKS_PATH}")
    contenido = DOCS_HOOKS_PATH.read_text(encoding="utf-8").lower()
    assert "hook" in contenido, "El doc debe explicar qué es un Hook"
    assert "connection" in contenido, "El doc debe explicar qué es una Connection"
    # Debe explicar la diferencia (el Hook usa/consume la Connection).
    assert "diferencia" in contenido or "resumen" in contenido, (
        "El doc debe explicar la diferencia entre Hook y Connection"
    )


def test_dag_usa_empty_operator_con_alias_dummy(dag_source: str) -> None:
    # Airflow 2.x: EmptyOperator es el reemplazo de DummyOperator (eliminado en
    # 2.7+). El alias mantiene la intención del enunciado por compatibilidad.
    assert "EmptyOperator" in dag_source
    assert "DummyOperator" in dag_source


def test_dag_task_ids_presentes(dag_source: str) -> None:
    # N >= 4 (task_1..task_4) + start/end + la tarea time_diff.
    for task_id in ("start", "end", "time_diff", "task_1", "task_2", "task_3", "task_4"):
        assert f'"{task_id}"' in dag_source or f"'{task_id}'" in dag_source, (
            f"Falta el task_id {task_id!r}"
        )


# ------------------------------------------------------------------
# Tests de importación/gráfico (opcionales).
# Se ejecutan solo si Airflow está instalado (p. ej. dentro del contenedor del
# compose). Localmente, sin Airflow, se omiten sin error.
# ------------------------------------------------------------------


@pytest.fixture(scope="module")
def airflow_dag():
    """Carga el DAG `test` en un DagBag. Se omite si Airflow no está instalado."""
    pytest.importorskip("airflow")
    from airflow.models import DagBag

    bag = DagBag(dag_folder=str(REPO_ROOT / "dags"), include_examples=False)
    assert not bag.import_errors, f"Errores al importar el DAG: {bag.import_errors}"
    dag = bag.get_dag("test")
    assert dag is not None, "El DAG 'test' no se registró en el DagBag"
    return dag


@pytest.fixture(scope="module")
def time_diff_cls():
    """Expone la clase ``TimeDiff`` importando ``dags/test.py``.
    Se omite si Airflow no está instalado."""
    pytest.importorskip("airflow")
    import importlib.util

    spec = importlib.util.spec_from_file_location("alten_test_dag", DAG_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.TimeDiff


def test_dag_carga_sin_errores(airflow_dag) -> None:
    # El DAG `test` debe registrarse limpiamente en el DagBag.
    assert airflow_dag.dag_id == "test"


def test_dag_tiene_siete_tareas(airflow_dag) -> None:
    # start + end + 4 dummy + time_diff = 7 tareas.
    esperados = {"start", "end", "time_diff", "task_1", "task_2", "task_3", "task_4"}
    assert set(airflow_dag.task_ids) == esperados


def test_tareas_pares_dependen_de_todas_las_impares(airflow_dag) -> None:
    # Las pares (task_2, task_4) deben tener como upstream todas las impares.
    for par in ("task_2", "task_4"):
        assert set(airflow_dag.task_dict[par].upstream_task_ids) == {"task_1", "task_3"}


def test_tareas_impares_no_dependen_de_otras_dummy(airflow_dag) -> None:
    # Las impares solo dependen de `start` (ningún task_n entre sus upstream).
    for impar in ("task_1", "task_3"):
        upstreams = set(airflow_dag.task_dict[impar].upstream_task_ids)
        assert upstreams == {"start"}, f"{impar} upstream inesperado: {upstreams}"


def test_start_precede_a_end_sin_ciclos(airflow_dag) -> None:
    # `end` está detrás de `start` y del flujo; el orden topológico no cicla.
    orden = [t.task_id for t in airflow_dag.topological_sort()]
    assert orden.index("start") < orden.index("end")
    assert orden.index("time_diff") < orden.index("end")


def test_time_diff_execute_registra_diferencia(time_diff_cls, caplog) -> None:
    # Triangulación caso 1: la fecha de referencia aparece en el log.
    # ``BaseOperator.log`` hereda de ``LoggingMixin`` como propiedad de solo
    # lectura (no admite ``setattr``), por lo que se captura con ``caplog`` vía
    # el framework estándar ``logging`` en lugar de reemplazarla con
    # ``monkeypatch``.
    op = time_diff_cls(task_id="t1", diff_date="2024-01-01")
    with caplog.at_level(logging.INFO):
        op.execute(context={})
    assert caplog.records, "TimeDiff.execute no registró ningún mensaje"
    assert "2024-01-01" in caplog.text


def test_time_diff_execute_con_otra_fecha(time_diff_cls, caplog) -> None:
    # Triangulación caso 2: otra fecha produce un log distinto con esa fecha.
    op = time_diff_cls(task_id="t2", diff_date="2000-06-15")
    with caplog.at_level(logging.INFO):
        op.execute(context={})
    assert "2000-06-15" in caplog.text
