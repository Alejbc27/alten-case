"""Prueba de humo: verifica que el paquete se importa correctamente.

Esta prueba no valida lógica de negocio (aún no existe). Su propósito es
confirmar que el `src layout` y la configuración de `pyproject.toml` funcionan.
"""

import importlib

import alten_pipeline


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
