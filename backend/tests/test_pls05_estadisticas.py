"""PLS-05 · Agregados estadísticos por grupo (stats).

HU 1, 4, 5, 14, 17, 19 y 22: promedio por grupo, tamaño de muestra (n),
participación, diferencia frente al promedio general y ranking. Los valores
esperados se calculan a mano (oráculo independiente) y se comparan con la API.
Semántica (HU 14): n debe ser el número de estudiantes con los que se
calculó el promedio global del grupo.
"""
import pytest

import file_api
from conftest import build_cache, install_cache, make_row

DATA = [  # (estrato, global, inglés)
    ("Estrato 1", "210", "40"), ("Estrato 1", "230", ""), ("Estrato 1", "250", "50"),
    ("Estrato 3", "300", "70"), ("Estrato 3", "320", "72"),
    ("", "260", "55"),
]


@pytest.fixture
def stats_data(positions, fresh_state):
    rows = [make_row(ESTU_CONSECUTIVO=f"S{i}", FAMI_ESTRATOVIVIENDA=s, PUNT_GLOBAL=g, PUNT_INGLES=e)
            for i, (s, g, e) in enumerate(DATA)]
    install_cache(build_cache(rows, positions))
    return file_api.stats(group_by="stratum")


def by_value(payload):
    return {g["value"]: g for g in payload["groups"]}


def test_promedios_coinciden_con_calculo_manual(stats_data):
    groups = by_value(stats_data)
    assert groups["Estrato 1"]["averages"]["score_global"] == 230.0
    assert groups["Estrato 3"]["averages"]["score_global"] == 310.0
    assert groups["Estrato 1"]["averages"]["score_english"] == 45.0  # el ausente no cuenta


def test_promedio_general_y_diferencias(stats_data):
    overall = (210 + 230 + 250 + 300 + 320 + 260) / 6
    assert stats_data["overall_average_global"] == round(overall, 1)
    assert by_value(stats_data)["Estrato 3"]["diff_global"] == round(310 - overall, 1)


def test_n_y_participacion(stats_data):
    groups = by_value(stats_data)
    assert sum(g["count"] for g in stats_data["groups"]) == stats_data["total_records"] == 6
    assert groups["Estrato 1"]["count"] == 3 and groups["Estrato 1"]["share"] == 50.0
    assert sum(g["share"] for g in stats_data["groups"]) == pytest.approx(100, abs=0.05)


def test_grupo_sin_dato_se_reporta_aparte(stats_data):
    assert by_value(stats_data)[None]["count"] == 1


def test_ranking_descendente(stats_data):
    averages = [g["averages"]["score_global"] for g in stats_data["groups"]]
    assert averages == sorted(averages, reverse=True)


def test_group_by_invalido_responde_422(fresh_state):
    with pytest.raises(file_api.HTTPException) as error:
        file_api.stats(group_by="internet; DROP TABLE")
    assert error.value.status_code == 422


def test_resultado_se_reutiliza_desde_cache(stats_data):
    assert file_api.stats(group_by="stratum") is stats_data


def test_semantica_n_coincide_con_datos_promediados(positions, fresh_state):
    """Un registro con PUNT_GLOBAL=-5 se acepta en la carga, pero en la caché
    -5 significa 'ausente'. Esperado: n del grupo = estudiantes promediados."""
    rows = [make_row(ESTU_CONSECUTIVO=f"S{i}", PUNT_GLOBAL=g) for i, g in enumerate(["250", "270", "-5"])]
    install_cache(build_cache(rows, positions))
    group = file_api.stats(group_by="period")["groups"][0]
    assert group["averages"]["score_global"] == 260.0
    assert group["count"] == 2, f"n reportado={group['count']} pero solo 2 puntajes se promediaron"
