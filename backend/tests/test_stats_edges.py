"""Pruebas adicionales de agregados: todos los agrupamientos y casos limite."""
from __future__ import annotations

import pytest

import file_api
from conftest import build_cache, install_cache, make_row


@pytest.mark.parametrize("field", file_api.GROUPABLE_FIELDS)
def test_todos_los_campos_agrupables_funcionan(field, positions, fresh_state):
    install_cache(build_cache([make_row()], positions))

    payload = file_api.stats(group_by=field)

    assert payload["group_by"] == field
    assert len(payload["groups"]) == 1
    assert payload["groups"][0]["count"] == 1
    assert payload["groups"][0]["value"] is not None


def test_empates_mantienen_orden_determinista(positions, fresh_state):
    rows = [
        make_row(ESTU_CONSECUTIVO="S1", ESTU_DEPTO_RESIDE="VALL", PUNT_GLOBAL="300"),
        make_row(ESTU_CONSECUTIVO="S2", ESTU_DEPTO_RESIDE="CAUCA", PUNT_GLOBAL="300"),
    ]
    install_cache(build_cache(rows, positions))

    groups = file_api.stats(group_by="department")["groups"]

    assert [group["value"] for group in groups] == ["VALLE", "CAUCA"]


def test_n_y_participacion_ignoran_registros_sin_puntaje_global(positions, fresh_state):
    cache = file_api.DatasetCache()
    sin_global = file_api.clean_record(make_row(ESTU_CONSECUTIVO="S1", PUNT_GLOBAL="250"), positions)
    sin_global["score_global"] = None
    cache.add(sin_global)
    cache.add(file_api.clean_record(make_row(ESTU_CONSECUTIVO="S2", PUNT_GLOBAL="270"), positions))
    install_cache(cache)

    payload = file_api.stats(group_by="period")
    group = payload["groups"][0]

    assert payload["total_records"] == 2
    assert group["count"] == 1
    assert group["averages"]["score_global"] == 270.0
    assert group["share"] == 50.0


def test_stats_reutiliza_la_cache_por_grupo(positions, fresh_state):
    install_cache(build_cache([make_row()], positions))

    first = file_api.stats(group_by="gender")
    second = file_api.stats(group_by="gender")

    assert second is first
