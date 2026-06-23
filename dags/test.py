"""DAG `test` (parte 3 - Prueba Técnica Alten).

DAG diario (03:00 UTC, cron ``0 3 * * *``) con tareas no-op, dependencias
par/impar y un operador personalizado ``TimeDiff`` que loguea la diferencia
temporal respecto a una fecha de referencia. Usa ``EmptyOperator`` con alias
``DummyOperator`` (este último se eliminó en Airflow 2.7+).
"""

from __future__ import annotations

from datetime import datetime, timedelta

from airflow.models import DAG
from airflow.models.baseoperator import BaseOperator
from airflow.operators.empty import EmptyOperator

# DummyOperator se eliminó en Airflow 2.7+. ``EmptyOperator`` es el operador
# no-op canónico de Airflow 2.x; se aliasa como ``DummyOperator`` para honrar la
# nomenclatura del enunciado y mantener la legibilidad del flujo.
DummyOperator = EmptyOperator

# Hook: código que usa una Connection (credenciales) almacenada en Airflow.
# Detalle y diferencia Hook vs Connection: docs/airflow-hooks-vs-connections.md


class TimeDiff(BaseOperator):
    """Operador que calcula y registra la diferencia temporal entre una fecha
    de referencia (``diff_date``) y el instante actual (UTC)."""

    def __init__(self, *, diff_date: str, **kwargs) -> None:
        super().__init__(**kwargs)
        self.diff_date = diff_date

    def execute(self, context):
        import pendulum

        ahora = pendulum.now("UTC")
        referencia = pendulum.parse(self.diff_date)
        diferencia = ahora - referencia
        self.log.info(
            "Diferencia entre %s y ahora (%s): %s",
            self.diff_date,
            ahora.to_iso8601_string(),
            diferencia.in_words(),
        )


# default_args exactos exigidos por el enunciado.
default_args = {
    "owner": "airflow",
    "depends_on_past": False,
    "start_date": datetime(1900, 1, 1),
    "retries": 1,
    "retry_delay": timedelta(seconds=5),
}


with DAG(
    dag_id="test",
    schedule="0 3 * * *",
    default_args=default_args,
    catchup=False,
    tags=["alten", "test"],
    doc_md=__doc__,
) as dag:
    start = DummyOperator(task_id="start")
    task_1 = DummyOperator(task_id="task_1")
    task_2 = DummyOperator(task_id="task_2")
    task_3 = DummyOperator(task_id="task_3")
    task_4 = DummyOperator(task_id="task_4")
    time_diff = TimeDiff(task_id="time_diff", diff_date="2024-01-01")
    end = DummyOperator(task_id="end")

    start >> task_1
    start >> task_3

    # Regla del enunciado: las tareas pares dependen de TODAS las impares.
    task_1 >> task_2
    task_3 >> task_2
    task_1 >> task_4
    task_3 >> task_4

    task_2 >> time_diff
    task_4 >> time_diff
    time_diff >> end
    start >> end
