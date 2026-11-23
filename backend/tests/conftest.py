"""Configuración común de las pruebas de lógica y semántica (Laboratorio 4).

Si FastAPI está instalado (venv del proyecto) se usa la librería real.
Si no lo está, se registra un sustituto mínimo que solo cubre lo que
file_api.py importa; las rutinas evaluadas son funciones Python puras,
por lo que el comportamiento lógico probado es el mismo.
"""
from __future__ import annotations

import sys
import types
from pathlib import Path

import pytest

BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

try:  # pragma: no cover - depende del entorno
    import fastapi  # noqa: F401
except ModuleNotFoundError:  # pragma: no cover
    class HTTPException(Exception):
        def __init__(self, status_code: int, detail=None):
            super().__init__(detail)
            self.status_code = status_code
            self.detail = detail

    class JSONResponse:
        def __init__(self, status_code: int = 200, content=None):
            self.status_code = status_code
            self.content = content

    class FastAPI:
        def __init__(self, *args, **kwargs):
            pass

        def add_middleware(self, *args, **kwargs):
            pass

        def get(self, *args, **kwargs):
            return lambda func: func

    def Query(default=None, **kwargs):
        return default

    fastapi_mod = types.ModuleType("fastapi")
    fastapi_mod.FastAPI, fastapi_mod.HTTPException, fastapi_mod.Query = FastAPI, HTTPException, Query
    cors_mod = types.ModuleType("fastapi.middleware.cors")
    cors_mod.CORSMiddleware = object
    responses_mod = types.ModuleType("fastapi.responses")
    responses_mod.JSONResponse = JSONResponse
    sys.modules.update({
        "fastapi": fastapi_mod,
        "fastapi.middleware": types.ModuleType("fastapi.middleware"),
        "fastapi.middleware.cors": cors_mod,
        "fastapi.responses": responses_mod,
    })

import file_api  # noqa: E402

HEADERS = list(file_api.FIELDS.values())


def make_row(**overrides) -> list[str]:
    """Construye una fila cruda del TSV con valores por defecto válidos."""
    base = {
        "ESTU_CONSECUTIVO": "SB11201940000001",
        "ESTU_GENERO": "F",
        "ESTU_FECHANACIMIENTO": "15/03/2002",
        "PERIODO": "20194",
        "ESTU_DEPTO_RESIDE": "VALLE",
        "ESTU_MCPIO_RESIDE": "TULUÁ",
        "FAMI_ESTRATOVIVIENDA": "Estrato 2",
        "ESTU_NSE_INDIVIDUAL": "NSE2",
        "FAMI_EDUCACIONMADRE": "Secundaria (Bachillerato) completa",
        "FAMI_EDUCACIONPADRE": "Primaria completa",
        "FAMI_TIENEINTERNET": "Si",
        "FAMI_TIENECOMPUTADOR": "Si",
        "COLE_NOMBRE_ESTABLECIMIENTO": "IE JULIA RESTREPO",
        "COLE_NATURALEZA": "OFICIAL",
        "COLE_AREA_UBICACION": "URBANO",
        "COLE_JORNADA": "MAÑANA",
        "COLE_CALENDARIO": "A",
        "COLE_BILINGUE": "N",
        "PUNT_LECTURA_CRITICA": "55",
        "PUNT_MATEMATICAS": "52",
        "PUNT_C_NATURALES": "50",
        "PUNT_SOCIALES_CIUDADANAS": "48",
        "PUNT_INGLES": "51",
        "PUNT_GLOBAL": "260",
        "PERCENTIL_GLOBAL": "55",
        "DESEMP_INGLES": "A1",
    }
    base.update(overrides)
    return [base[column] for column in HEADERS]


@pytest.fixture
def positions() -> dict[str, int]:
    return {name: HEADERS.index(column) for name, column in file_api.FIELDS.items()}


@pytest.fixture
def fresh_state():
    """Deja el estado global de la API limpio antes y después de cada prueba."""
    def reset():
        file_api.DATASET_CACHE = None
        file_api.FILTER_CACHE_KEY = None
        file_api.FILTER_CACHE_INDICES = None
        file_api.STATS_CACHE = {}
        file_api.LAST_ACCESS = 0.0
    reset()
    yield file_api
    reset()


def build_cache(rows: list[list[str]], positions: dict[str, int]) -> "file_api.DatasetCache":
    cache = file_api.DatasetCache()
    for raw in rows:
        record = file_api.clean_record(raw, positions)
        if record:
            cache.add(record)
    return cache


def install_cache(cache) -> None:
    import time
    file_api.DATASET_CACHE = cache
    file_api.LAST_ACCESS = time.monotonic()
