"""Prueba de humo: verifica que el paquete se importa correctamente.

Esta prueba no valida lógica de negocio (aún no existe). Su propósito es
confirmar que el `src layout` y la configuración de `pyproject.toml` funcionan.
"""

import importlib
import os
import subprocess
import sys
from pathlib import Path

import alten_pipeline

#: Raíz `src/` del proyecto, para ponerla en PYTHONPATH del subproceso.
_SRC_DIR = Path(__file__).resolve().parent.parent / "src"


def test_paquete_importable() -> None:
    """El paquete `alten_pipeline` debe poder importarse."""
    assert alten_pipeline is not None


def test_version_definida() -> None:
    """El paquete debe exponer un atributo `__version__`."""
    assert hasattr(alten_pipeline, "__version__")
    assert isinstance(alten_pipeline.__version__, str)
    assert alten_pipeline.__version__ != ""


def test_modulo_recargable() -> None:
    """El paquete debe ser recargable sin errores (idempotencia de import)."""
    reloaded = importlib.reload(alten_pipeline)
    assert reloaded is alten_pipeline


def test_importar_paquete_no_precarga_submodulo_main() -> None:
    """Importar `alten_pipeline` NO debe cargar el submódulo `main` en memoria.

    Si `__init__.py` importara `.main`, el submódulo quedaría en `sys.modules`
    al importar el paquete, y al ejecutar `python -m alten_pipeline.main` runpy
    emitiría ``RuntimeWarning: 'alten_pipeline.main' found in sys.modules after
    import of package 'alten_pipeline', but prior to execution``. Lo verificamos
    en un intérprete limpio (sin imports previos) para aislar el comportamiento.
    """
    codigo = (
        "import sys; import alten_pipeline; "
        "sys.exit(0 if 'alten_pipeline.main' not in sys.modules else 1)"
    )
    entorno = {**os.environ, "PYTHONPATH": str(_SRC_DIR)}
    resultado = subprocess.run(
        [sys.executable, "-c", codigo],
        env=entorno,
        capture_output=True,
        text=True,
    )
    assert resultado.returncode == 0, (
        "importar alten_pipeline precargó alten_pipeline.main en sys.modules; "
        f"eso dispara el RuntimeWarning de runpy. stderr={resultado.stderr!r}"
    )


def test_paquete_no_exporta_main_ni_run_en_all() -> None:
    """El paquete no debe exponer `main`/`run` como API pública.

    Exportarlos obligaría a importar el submódulo `main` desde `__init__.py`,
    lo que precarga el módulo y provoca el ``RuntimeWarning`` de `python -m
    alten_pipeline.main`. El entrypoint se invoca vía submódulo, no vía paquete.
    """
    assert "main" not in alten_pipeline.__all__
    assert "run" not in alten_pipeline.__all__
