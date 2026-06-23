"""Validación estructural de la infraestructura Terraform (parte 4).

Estos tests NO aplican Terraform contra GCP (no hay credenciales en CI).
Verifican que la configuración HCL exista y cumpla los requisitos de
infraestructura Terraform y el contrato de la prueba:

- estructura de archivos esperada en ``terraform/`` y sus módulos
- versiones pinadas (terraform, google, local)
- backend ``gcs`` vacío con bucket vía ``-backend-config`` (nada hardcodeado)
- provider google con project y region tomados de variables
- variables requeridas con defaults sensatos
- datasets ``SANDBOX_alten_pipeline`` e ``INTEGRATION``
- schemas explícitos de ``raw_breweries`` (15 columnas) e
  ``integration_prueba_tecnica`` (10 columnas), alineados con
  ``api_client._normalize()`` y ``sql/transform.sql``
- service account con ``jobUser`` (proyecto) y ``dataEditor`` (datasets),
  ``google_service_account_key`` y ``local_sensitive_file``
- ``.gitignore`` cubre tfvars, ``.terraform``, tfstate, tfplan, ``.secrets/``
  y las claves JSON
- ``terraform.tfvars.example`` sin secretos
- sin directorio legacy ``infra/terraform/``
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
TF_ROOT = REPO_ROOT / "terraform"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _read(rel: str) -> str:
    """Lee un archivo bajo ``terraform/`` fallando a nivel de pytest si falta."""
    path = TF_ROOT / rel
    if not path.is_file():
        pytest.fail(f"No existe el archivo de producción: {path}")
    return path.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# Estructura de archivos
# ---------------------------------------------------------------------------
def test_estructura_de_archivos_espera_existe() -> None:
    # Raíz orquestadora + dos módulos.
    esperados = [
        "versions.tf",
        "backend.tf",
        "providers.tf",
        "variables.tf",
        "main.tf",
        "outputs.tf",
        "terraform.tfvars.example",
        "modules/bigquery/variables.tf",
        "modules/bigquery/main.tf",
        "modules/bigquery/outputs.tf",
        "modules/service_account/variables.tf",
        "modules/service_account/main.tf",
        "modules/service_account/outputs.tf",
    ]
    faltantes = [rel for rel in esperados if not (TF_ROOT / rel).is_file()]
    assert not faltantes, f"Faltan archivos: {faltantes}"


def test_no_existe_directorio_legacy_infra_terraform() -> None:
    # Estructura esperada: terraform/ en la raíz del repo, sin directorio legacy.
    assert not (REPO_ROOT / "infra" / "terraform").exists()


# ---------------------------------------------------------------------------
# Versiones y provider
# ---------------------------------------------------------------------------
def test_versiones_pinadas() -> None:
    versions = _read("versions.tf")
    assert 'required_version = ">= 1.5"' in versions
    assert "hashicorp/google" in versions
    assert 'version = "~> 5.0"' in versions
    assert "hashicorp/local" in versions
    assert 'version = "~> 2.0"' in versions


def test_backend_gcs_vacio_sin_bucket_hardcodeado() -> None:
    backend = _read("backend.tf")
    assert 'backend "gcs" {}' in backend
    # El bucket NO se hardcodea: se pasa vía -backend-config en init.
    assert "bucket =" not in backend
    assert "-backend-config" in backend


def test_provider_usa_variables_para_project_y_region() -> None:
    providers = _read("providers.tf")
    assert "project = var.gcp_project" in providers
    assert "region  = var.gcp_region" in providers
    # Sin project/region literales en la configuración del provider.
    assert '"alten-case"' not in providers
    assert '"europe-west1"' not in providers


# ---------------------------------------------------------------------------
# Variables
# ---------------------------------------------------------------------------
def test_variables_requeridas_con_defaults() -> None:
    variables = _read("variables.tf")
    for name in (
        "gcp_project",
        "gcp_region",
        "gcs_bucket",
        "sa_account_id",
        "sa_key_output_path",
        "dataset_names",
        "table_names",
    ):
        assert f'variable "{name}"' in variables, f"Falta variable {name!r}"

    assert 'default     = "alten-case"' in variables
    assert 'default     = "europe-west1"' in variables
    assert 'default     = "alten-pipeline-sa"' in variables


def test_dataset_names_incluye_los_dos_datasets() -> None:
    variables = _read("variables.tf")
    assert "SANDBOX_alten_pipeline" in variables
    assert "INTEGRATION" in variables


# ---------------------------------------------------------------------------
# BigQuery: schemas alineados con Python/SQL
# ---------------------------------------------------------------------------
# Contrato derivado de api_client._normalize() (15 columnas).
RAW_BREWERIES_SCHEMA = [
    ("id", "STRING", "NULLABLE"),
    ("name", "STRING", "NULLABLE"),
    ("brewery_type", "STRING", "NULLABLE"),
    ("street", "STRING", "NULLABLE"),
    ("city", "STRING", "NULLABLE"),
    ("state", "STRING", "NULLABLE"),
    ("country", "STRING", "NULLABLE"),
    ("postal_code", "STRING", "NULLABLE"),
    ("phone", "STRING", "NULLABLE"),
    ("website_url", "STRING", "NULLABLE"),
    ("longitude", "FLOAT64", "NULLABLE"),
    ("latitude", "FLOAT64", "NULLABLE"),
    ("ingestion_ts", "TIMESTAMP", "REQUIRED"),
    ("ingestion_run_id", "STRING", "REQUIRED"),
    ("source_payload", "STRING", "REQUIRED"),
]

# Contrato derivado de sql/transform.sql SELECT final (10 columnas).
INTEGRATION_SCHEMA = [
    ("brewery_id", "STRING", "REQUIRED"),
    ("name", "STRING", "NULLABLE"),
    ("brewery_type", "STRING", "NULLABLE"),
    ("city", "STRING", "NULLABLE"),
    ("state", "STRING", "NULLABLE"),
    ("country", "STRING", "NULLABLE"),
    ("phone", "STRING", "NULLABLE"),
    ("website_url", "STRING", "NULLABLE"),
    ("ingestion_ts", "TIMESTAMP", "NULLABLE"),
    ("transformation_date", "DATE", "NULLABLE"),
]


def _assert_schema(hcl: str, columns: list[tuple[str, str, str]]) -> None:
    for name, btype, mode in columns:
        triple = f'{{ name = "{name}", type = "{btype}", mode = "{mode}" }}'
        assert triple in hcl, f"Falta la columna {name!r} ({btype} {mode})"


def test_schema_raw_breweries_alineado_con_api_client() -> None:
    # 15 columnas, una por cada clave de api_client._normalize().
    hcl = _read("modules/bigquery/main.tf")
    _assert_schema(hcl, RAW_BREWERIES_SCHEMA)
    assert len(RAW_BREWERIES_SCHEMA) == 15


def test_schema_integration_alineado_con_transform_sql() -> None:
    # 10 columnas, una por cada columna del SELECT final de transform.sql.
    hcl = _read("modules/bigquery/main.tf")
    _assert_schema(hcl, INTEGRATION_SCHEMA)
    assert len(INTEGRATION_SCHEMA) == 10


def test_datasets_creados_en_el_modulo_bigquery() -> None:
    hcl = _read("modules/bigquery/main.tf")
    assert "google_bigquery_dataset" in hcl
    assert "google_bigquery_table" in hcl
    assert "for_each" in hcl


# ---------------------------------------------------------------------------
# Service Account
# ---------------------------------------------------------------------------
def test_service_account_y_permisos_minimos() -> None:
    hcl = _read("modules/service_account/main.tf")
    assert "google_service_account" in hcl
    assert "roles/bigquery.jobUser" in hcl
    assert "google_project_iam_member" in hcl
    assert "roles/bigquery.dataEditor" in hcl
    assert "google_bigquery_dataset_iam_member" in hcl


def test_service_account_key_y_local_sensitive_file() -> None:
    hcl = _read("modules/service_account/main.tf")
    assert "google_service_account_key" in hcl
    assert "local_sensitive_file" in hcl
    assert "private_key" in hcl


def test_service_account_key_es_opcional_con_count() -> None:
    # La clave y el archivo local solo se crean cuando create_key=true.
    hcl = _read("modules/service_account/main.tf")
    assert "count              = var.create_key ? 1 : 0" in hcl
    assert "count           = var.create_key ? 1 : 0" in hcl
    # La referencia a la clave usa indice [0] (valido cuando count=1).
    assert "google_service_account_key.this[0].private_key" in hcl


def test_modulo_service_account_define_variable_create_key() -> None:
    variables = _read("modules/service_account/variables.tf")
    assert 'variable "create_key"' in variables
    # Default defensivo en false: por defecto no se crea ninguna clave.
    assert "default     = false" in variables


def test_outputs_modulo_sa_soportan_create_key_false() -> None:
    # Cuando create_key=false, los outputs de la clave deben resolver a null.
    outputs = _read("modules/service_account/outputs.tf")
    assert "var.create_key ? local_sensitive_file.sa_key[0].filename : null" in outputs
    assert "var.create_key ? google_service_account_key.this[0].private_key : null" in outputs


# ---------------------------------------------------------------------------
# Variable raiz create_sa_key y cableo al modulo
# ---------------------------------------------------------------------------
def test_variable_raiz_create_sa_key_default_false() -> None:
    variables = _read("variables.tf")
    assert 'variable "create_sa_key"' in variables
    assert "type        = bool" in variables
    assert "default     = false" in variables


def test_raiz_cablea_create_sa_key_al_modulo() -> None:
    main = _read("main.tf")
    assert "create_key      = var.create_sa_key" in main


def test_tfvars_example_create_sa_key_false_y_sa_real() -> None:
    tfvars = _read("terraform.tfvars.example")
    assert 'create_sa_key = false' in tfvars
    # La SA real del usuario para el ejemplo.
    assert 'sa_account_id = "bq-alten-case"' in tfvars


def test_raiz_cablea_ambos_modulos() -> None:
    main = _read("main.tf")
    assert 'module "bigquery"' in main
    assert 'module "service_account"' in main
    # El módulo SA recibe los dataset_ids desde el módulo bigquery.
    assert "dataset_ids     = module.bigquery.dataset_ids" in main


def test_outputs_incluyen_sa_email_key_y_private_key_sensitive() -> None:
    outputs = _read("outputs.tf")
    assert "service_account_email" in outputs
    assert "sa_key_path" in outputs
    assert "sa_private_key" in outputs
    assert "sensitive   = true" in outputs


# ---------------------------------------------------------------------------
# Seguridad: .gitignore y tfvars sin secretos
# ---------------------------------------------------------------------------
@pytest.fixture(scope="module")
def gitignore() -> str:
    path = REPO_ROOT / ".gitignore"
    assert path.is_file(), "Falta .gitignore en la raíz del repo"
    return path.read_text(encoding="utf-8")


def test_gitignore_cubre_secrets_tfvars_estado_y_plan(gitignore: str) -> None:
    for patron in (
        ".terraform/",
        "*.tfvars",
        "*.tfplan",
        "terraform.tfstate",
        ".secrets/",
    ):
        assert patron in gitignore, f".gitignore no cubre {patron!r}"


def test_gitignore_cubre_claves_sa(gitignore: str) -> None:
    # La clave por defecto se escribe en .secrets/ (ya cubierto arriba); además
    # se ignora el nombre de archivo por si se ubica fuera de .secrets/.
    assert ".secrets/" in gitignore
    assert "*-sa.json" in gitignore or "alten-pipeline-sa.json" in gitignore


def _strip_comments(text: str) -> str:
    """Elimina comentarios ``# ...`` y ``// ...`` de línea (sintaxis tfvars/HCL)."""
    no_hash = re.sub(r"#.*$", "", text, flags=re.MULTILINE)
    return re.sub(r"//.*$", "", no_hash, flags=re.MULTILINE)


def test_tfvars_example_no_contiene_secretos() -> None:
    # Se ignoran los comentarios: interesa que ningún VALOR sea un secreto.
    tfvars = _strip_comments(_read("terraform.tfvars.example")).lower()
    for prohibido in ("private_key", "credentials", "password", "token"):
        assert prohibido not in tfvars, f"Posible secreto en tfvars.example: {prohibido!r}"
    # Sin un bloque de clave privada PEM incrustado.
    assert "begin private key" not in tfvars
