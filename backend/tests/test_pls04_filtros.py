"""PLS-04 · Filtrado combinado y paginación (matching_indices / records).

HU 2, 9, 11, 12, 13 y 15: filtrar por año, departamento, estrato, zona,
jornada y naturaleza, combinando varios filtros (conjunción lógica Y).
Semántica: filtered_records es el número exacto de estudiantes que cumplen
TODOS los filtros, y las páginas recorren ese conjunto sin repetir ni omitir.
"""
import pytest

import file_api
from conftest import build_cache, install_cache, make_row

NO_FILTERS = dict(period=None, gender=None, department=None, stratum=None,
                  school_nature=None, school_area=None, school_schedule=None)


@pytest.fixture
def dataset(positions, fresh_state):
    combos = [
        ("20191", "VALLE", "Estrato 1", "URBANO"), ("20194", "VALLE", "Estrato 2", "RURAL"),
        ("20194", "VALLE", "Estrato 2", "URBANO"), ("20201", "CAUCA", "Estrato 2", "URBANO"),
        ("20194", "CAUCA", "Estrato 1", "RURAL"), ("20194", "VALLE", "Estrato 2", "URBANO"),
        ("20211", "ANTIOQUIA", "Estrato 3", "URBANO"),
    ]
    rows = []
    for i in range(3):  # 21 registros
        for j, (p, d, s, a) in enumerate(combos):
            rows.append(make_row(ESTU_CONSECUTIVO=f"S{i}{j}", PERIODO=p, ESTU_DEPTO_RESIDE=d,
                                 FAMI_ESTRATOVIVIENDA=s, COLE_AREA_UBICACION=a))
    cache = build_cache(rows, positions)
    install_cache(cache)
    return cache


def call(page=1, page_size=20, **filters):
    return file_api.records(**{**NO_FILTERS, **filters}, page=page, page_size=page_size)


def test_sin_filtros_devuelve_todo(dataset):
    result = call()
    assert result["total_records"] == result["filtered_records"] == 21


def test_filtros_combinados_son_conjuncion(dataset):
    result = call(period="20194", department="VALLE", stratum="Estrato 2", school_area="URBANO")
    assert result["filtered_records"] == 6
    for r in result["records"]:
        assert (r["period"], r["department"], r["stratum"], r["school_area"]) == ("20194", "VALLE", "Estrato 2", "URBANO")


def test_valor_inexistente_devuelve_cero_sin_error(dataset):
    result = call(department="AMAZONAS")
    assert result["filtered_records"] == 0 and result["records"] == []


def test_paginas_cubren_el_conjunto_sin_repetir(dataset):
    seen = []
    for page in range(1, 6):
        seen += [r["student_code"] for r in call(page=page, page_size=5)["records"]]
    assert len(seen) == 21 and len(set(seen)) == 21
    assert len(call(page=5, page_size=5)["records"]) == 1  # última página parcial
    assert call(page=6, page_size=5)["records"] == []      # página fuera de rango


def test_cache_de_filtro_se_invalida_al_cambiar_filtros(dataset):
    a = call(department="VALLE")["filtered_records"]
    b = call(department="CAUCA")["filtered_records"]
    c = call(department="VALLE")["filtered_records"]
    assert (a, b, c) == (12, 6, 12)


def test_opciones_de_filtro_ordenadas_y_sin_nulos(dataset):
    filters = call()["filters"]
    assert filters["period"] == ["20191", "20194", "20201", "20211"]
    assert None not in filters["stratum"]


def test_sin_archivo_responde_503(tmp_path, monkeypatch, fresh_state):
    monkeypatch.setattr(file_api, "DATASET_PATH", tmp_path / "no_existe.csv")
    monkeypatch.setitem(file_api.LOAD_STATE, "status", "idle")
    with pytest.raises(file_api.HTTPException) as error:
        call()
    assert error.value.status_code == 503
