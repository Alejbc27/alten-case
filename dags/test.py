"""DAG de prueba `test` (parte 3 - Prueba Técnica Alten).

DAG diario (03:00 UTC) con tareas Dummy, una estructura de dependencias
par/impar y un operador personalizado ``TimeDiff`` que loguea la diferencia
temporal respecto a una fecha de referencia.

Requisitos del enunciado cubiertos:
    - ``dag_id='test'`` y schedule ``0 3 * * *`` (03:00 UTC diario).
    - ``default_args`` exactos (owner airflow, start_date 1900-01-01, 1 retry,
      ``retry_delay`` de 5 s).
    - ``catchup=False`` para evitar un backfill masivo desde 1900.
    - ``start``/``end`` con operador no-op (``EmptyOperator`` en Airflow 2,
      con alias ``DummyOperator`` por compatibilidad con la nomenclatura del
      enunciado).
    - ``task_1``..``task_4`` donde las tareas pares (``task_2``, ``task_4``)
      dependen de todas las impares (``task_1``, ``task_3``).
    - Una tarea ``time_diff`` basada en el operador ``TimeDiff``.
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

# ------------------------------------------------------------------
# Hook vs Connection (conceptos de Airflow)
# ------------------------------------------------------------------
# - Hook: interfaz programática (código) que sabe *cómo* comunicarse con un
#   servicio externo (p. ej. PostgresHook, HttpHook). Encapsula la lógica de
#   conexión y las llamadas a la API/protocolo subyacente.
# - Connection: la *configuración/credenciales* almacenadas en la metadata DB
#   de Airflow (o en variables de entorno) que el Hook lee para saber *a quién*
#   conectarse: host, login, password, schema y parámetros ``extra``.
#   Es el dato; el Hook es el comportamiento que lo consume.
# En resumen: la Connection guarda las credenciales/configuración y el Hook es
# el código que las usa para ejecutar la integración.
# ------------------------------------------------------------------


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

    # Las tareas impares arrancan tras `start`.
    start >> task_1
    start >> task_3

    # Las tareas pares dependen de TODAS las impares (cada par → todas las impares).
    task_1 >> task_2
    task_3 >> task_2
    task_1 >> task_4
    task_3 >> task_4

    # `time_diff` va detrás del flujo; `end` detrás de `start` y de `time_diff`.
    task_2 >> time_diff
    task_4 >> time_diff
    time_diff >> end
    start >> end
