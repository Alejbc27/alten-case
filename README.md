# alten-case

Pipeline de datos para la **prueba técnica de Alten** (perfil Data Engineer). El objetivo es construir una solución de ingesta, transformación y carga sobre **Google BigQuery**, orquestada con **Apache Airflow** y con la infraestructura definida como código con **Terraform**.

Este repositorio contiene el andamiaje inicial (`scaffold`) del proyecto. La lógica completa se incorpora en fases posteriores.

> **Nota sobre los requisitos:** el enunciado oficial se recibió por correo y se conserva fuera del repositorio público. La prueba permite elegir cualquier API, exige cargar datos en BigQuery, transformar con SQL idempotente y orquestar un proceso con Airflow.

- **Repo:** https://github.com/Alejbc27/alten-case
- **Rama base:** `chore/project-scaffold`

## Estado actual

| Aspecto | Estado |
|---------|--------|
| Estructura de carpetas | Listo |
| Configuración de proyecto (`pyproject.toml`) | Listo |
| `.gitignore` | Listo |
| Lógica de ingesta | Pendiente |
| SQL final | Pendiente |
| DAGs de Airflow | Pendiente |
| Infraestructura Terraform | Pendiente |
| CI/CD | Pendiente |

## Alcance de la prueba

Construir una pipeline reproducible e idempotente que:

1. **Ingiera** al menos 100 registros desde una API pública.
2. **Cargue** los datos crudos en un dataset `SANDBOX_<nombre_aplicacion>` de BigQuery.
3. **Transforme** los datos con SQL idempotente hacia `INTEGRATION.integration_prueba_tecnica`.
4. **Orqueste** el flujo con Airflow.
5. **Provisione** la infraestructura con Terraform (como extra controlado).

El detalle completo de los requisitos se mantiene en el enunciado recibido por correo.

## Estructura prevista

```
alten-case/
├── src/alten_pipeline/     # Código Python del proyecto (paquete)
├── tests/                  # Pruebas (pytest)
├── sql/                    # Consultas SQL finales
├── dags/                   # DAGs de Apache Airflow
├── infra/terraform/        # Infraestructura como código (GCP)
├── pyproject.toml          # Configuración del proyecto y herramientas
├── .python-version         # Versión de Python recomendada (3.11)
├── .gitignore
└── README.md
```

## Cómo empezar (cuando esté implementado)

```bash
# 1. Versión de Python recomendada
python --version   # se espera 3.11+

# 2. Crear entorno virtual
python -m venv .venv
source .venv/bin/activate

# 3. Instalar el paquete en modo desarrollo
pip install -e ".[dev]"

# 4. Ejecutar pruebas
pytest
```

> El entorno virtual y las credenciales de GCP **no** se versionan. Ver `.gitignore`.

## Próximos pasos

1. Implementar la capa de ingesta (`src/alten_pipeline/`).
2. Definir el SQL final en `sql/`.
3. Crear el DAG de orquestación en `dags/`.
4. Provisionar infraestructura con Terraform en `infra/terraform/`.
