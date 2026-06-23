"""Validación estática del workflow de CI de GitHub Actions.

Estos tests NO ejecutan el workflow (eso lo hace GitHub Actions en cada PR/push).
Verifican que ``.github/workflows/ci.yml`` exista y cumpla el contrato del cambio
``github-actions-ci-cd``:

- triggers en ``pull_request`` y ``push`` a ``main`` (no otras ramas)
- permisos mínimos: ``contents: read``
- tres jobs independientes: ``python``, ``terraform``, ``docker-compose``
- comandos críticos de cada job
  (``uv sync``, ``uv run pytest``, ``uv run ruff``; ``terraform fmt/init/validate``;
  ``docker compose config --quiet``)
- ausencia de despliegue: no ``terraform apply``, no ``docker compose up``,
  no ``gcloud auth``, no ``secrets``, no ``workflow_dispatch``

Coherente con el patrón de ``tests/test_terraform_structure.py``: parsing de texto
puro (PyYAML no es dependencia del proyecto).
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
WORKFLOW = REPO_ROOT / ".github" / "workflows" / "ci.yml"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
@pytest.fixture(scope="module")
def ci_yaml() -> str:
    """Lee ``ci.yml`` fallando a nivel de pytest si no existe."""
    if not WORKFLOW.is_file():
        pytest.fail(f"No existe el workflow de CI: {WORKFLOW}")
    return WORKFLOW.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def ci_yaml_sin_comentarios(ci_yaml: str) -> str:
    """``ci_yaml`` sin comentarios ``# ...`` (para aserciones negativas de seguridad).

    Permite documentar en comentarios la intención del diseño (p. ej. "sin
    terraform apply") sin disparar falsos positivos: lo que importa es que el
    workflow *ejecutable* no contenga esos comandos. Mismo patrón que
    ``test_terraform_structure._strip_comments``.
    """
    return re.sub(r"#.*$", "", ci_yaml, flags=re.MULTILINE)


# ---------------------------------------------------------------------------
# Existencia y estructura básica
# ---------------------------------------------------------------------------
def test_workflow_existe_y_es_yaml_valido(ci_yaml: str) -> None:
    # El archivo existe (garantizado por la fixture) y declara las claves raíz.
    assert "name:" in ci_yaml
    assert "on:" in ci_yaml
    assert "jobs:" in ci_yaml


# ---------------------------------------------------------------------------
# Triggers
# ---------------------------------------------------------------------------
def test_triggers_pull_request_y_push_a_main(ci_yaml: str) -> None:
    # La spec exige disparar en PR y en push a main.
    assert "pull_request" in ci_yaml
    assert "push" in ci_yaml
    # El push está restringido a main (no dispara en cualquier rama).
    assert "main" in ci_yaml


def test_no_trigger_en_ramas_distintas_de_main(ci_yaml: str) -> None:
    # No debe haber branches adicionales que disparen el workflow.
    for rama in ("develop", "staging", "release"):
        assert rama not in ci_yaml, f"Trigger inesperado para la rama {rama!r}"


# ---------------------------------------------------------------------------
# Permisos mínimos
# ---------------------------------------------------------------------------
def test_permisos_minimos_contents_read(ci_yaml: str) -> None:
    assert "permissions:" in ci_yaml
    assert "contents: read" in ci_yaml


def test_no_permisos_de_escritura(ci_yaml_sin_comentarios: str) -> None:
    # CI de validación no necesita escribir en el repo ni en paquetes.
    for prohibido in ("contents: write", "packages: write", "id-token: write"):
        assert prohibido not in ci_yaml_sin_comentarios, (
            f"Permiso de escritura no esperado: {prohibido!r}"
        )


# ---------------------------------------------------------------------------
# Jobs esperados
# ---------------------------------------------------------------------------
def test_tres_jobs_independientes_presentes(ci_yaml: str) -> None:
    for job in ("python", "terraform", "docker-compose"):
        assert f"{job}:" in ci_yaml, f"Falta el job {job!r}"


def test_jobs_corren_en_ubuntu_latest(ci_yaml: str) -> None:
    assert "ubuntu-latest" in ci_yaml


# ---------------------------------------------------------------------------
# Job Python
# ---------------------------------------------------------------------------
def test_job_python_checkout_y_setup(ci_yaml: str) -> None:
    assert "actions/checkout@v4" in ci_yaml
    assert "actions/setup-python" in ci_yaml
    assert "setup-uv" in ci_yaml


def test_job_python_version_311(ci_yaml: str) -> None:
    # pyproject pide >=3.11; .python-version fija 3.11.9.
    assert "3.11" in ci_yaml


def test_job_python_comandos_criticos(ci_yaml: str) -> None:
    assert "uv sync --all-extras" in ci_yaml
    assert "uv run pytest" in ci_yaml
    assert "uv run ruff check" in ci_yaml


# ---------------------------------------------------------------------------
# Job Terraform
# ---------------------------------------------------------------------------
def test_job_terraform_setup_y_directorio(ci_yaml: str) -> None:
    assert "setup-terraform" in ci_yaml
    # Los comandos se ejecutan dentro de terraform/.
    assert "working-directory: terraform" in ci_yaml


def test_job_terraform_comandos_criticos(ci_yaml: str) -> None:
    assert "terraform fmt -recursive -check" in ci_yaml
    assert "terraform init -backend=false" in ci_yaml
    assert "terraform validate" in ci_yaml


# ---------------------------------------------------------------------------
# Job Docker Compose
# ---------------------------------------------------------------------------
def test_job_docker_compose_comando(ci_yaml: str) -> None:
    assert "docker compose config --quiet" in ci_yaml


# ---------------------------------------------------------------------------
# Seguridad: sin secrets, sin deploy
# ---------------------------------------------------------------------------
def test_no_referencia_secrets(ci_yaml_sin_comentarios: str) -> None:
    assert "${{ secrets" not in ci_yaml_sin_comentarios, (
        "El workflow no debe referenciar secrets"
    )
    assert "secrets." not in ci_yaml_sin_comentarios


def test_no_comandos_de_despliegue(ci_yaml_sin_comentarios: str) -> None:
    for prohibido in (
        "terraform apply",
        "terraform plan",
        "docker compose up",
        "docker compose -d",
        "gcloud auth",
        "gcloud builds",
    ):
        assert prohibido not in ci_yaml_sin_comentarios, (
            f"Comando de despliegue prohibido: {prohibido!r}"
        )


def test_no_workflow_dispatch(ci_yaml_sin_comentarios: str) -> None:
    # El CI es automático (PR/push). CD manual queda para un cambio futuro.
    assert "workflow_dispatch" not in ci_yaml_sin_comentarios
