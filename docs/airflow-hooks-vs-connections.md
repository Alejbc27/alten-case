# Hooks vs Connections en Airflow

La **Connection** guarda las credenciales y la configuración de un servicio externo;
el **Hook** es el código que las usa para comunicarse con ese servicio. En una
frase: una Connection es *dato*; un Hook es *comportamiento*.

## Qué es cada cosa

| Concepto | Qué es | Dónde vive | Ejemplos |
|----------|--------|-----------|----------|
| **Hook** | Interfaz programática (código) que sabe *cómo* hablar con un servicio: protocolo, llamadas y manejo de respuestas. | En el código del operador o tarea | `PostgresHook`, `HttpHook`, `S3Hook` |
| **Connection** | Registro de *a quién* conectarse y *con qué credenciales*: host, login, password, schema, puerto y `extra`. | Metadata DB de Airflow (UI → Admin → Connections) o variables de entorno | `ConnId = "mi_api"` |

## Diferencia principal

- La **Connection** responde *"¿a dónde y con qué credenciales?"*.
- El **Hook** responde *"¿cómo hablo con ese servicio?"*: abre la conexión,
  ejecuta la consulta o llamada y cierra los recursos.

Un Hook no tiene credenciales propias: las pide a Airflow a partir de un `conn_id`,
y Airflow le entrega la Connection correspondiente.

## Ejemplo mínimo

```python
from airflow.providers.postgres.hooks.postgres import PostgresHook

# El Hook solo conoce el conn_id; las credenciales las provee la Connection.
hook = PostgresHook(postgres_conn_id="mi_postgres")
filas = hook.get_records("SELECT 1")
```

Para que ese código funcione debe existir una **Connection** `mi_postgres`,
configurada en *Admin → Connections* o como variable de entorno
`AIRFLOW_CONN_MI_POSTGRES`.

## Referencias

- [Connections — Apache Airflow](https://airflow.apache.org/docs/apache-airflow/stable/howto/connection.html)
- [Hooks — Apache Airflow](https://airflow.apache.org/docs/apache-airflow/stable/extending-airflow/hooks.html)
