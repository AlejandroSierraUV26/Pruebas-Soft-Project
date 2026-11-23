"""Pruebas de limites de la escala ICFES y de fechas de nacimiento."""
from __future__ import annotations

import pytest

import file_api
from conftest import make_row


@pytest.mark.parametrize("column,value", [
    ("PUNT_GLOBAL", "0"),
    ("PUNT_GLOBAL", "500"),
    ("PUNT_MATEMATICAS", "0"),
    ("PUNT_MATEMATICAS", "100"),
    ("PERCENTIL_GLOBAL", "100"),
])
def test_acepta_puntajes_en_los_limites(positions, column, value):
    record = file_api.clean_record(make_row(**{column: value}), positions)
    assert record is not None
    assert record[{"PUNT_GLOBAL": "score_global", "PUNT_MATEMATICAS": "score_math",
                   "PERCENTIL_GLOBAL": "percentile_global"}[column]] == float(value)


@pytest.mark.parametrize("column,value", [
    ("PUNT_GLOBAL", "-0.1"),
    ("PUNT_GLOBAL", "500.1"),
    ("PUNT_GLOBAL", "nan"),
    ("PUNT_GLOBAL", "inf"),
    ("PUNT_MATEMATICAS", "-0.1"),
    ("PUNT_MATEMATICAS", "100.1"),
])
def test_rechaza_puntajes_fuera_de_la_escala(positions, column, value):
    assert file_api.clean_record(make_row(**{column: value}), positions) is None


@pytest.mark.parametrize("birth,expected", [
    ("29/02/2000", 19.0),  # ano bisiesto
    ("29/02/2001", None),  # fecha inexistente
    ("31/02/2000", None),  # fecha inexistente
    ("00/01/2000", None),  # dia invalido
    ("01/13/2000", None),  # mes invalido
])
def test_edad_valida_fechas_reales(birth, expected):
    assert file_api.age_at_exam(birth, 20194) == expected


def test_edad_antes_del_cumpleanos():
    # Nacido en diciembre: en agosto de 2019 todavia tiene 17, no 18.
    assert file_api.age_at_exam("20/12/2001", 20194) == 17.0
    # Nacido en marzo: en agosto de 2019 ya cumplio 17.
    assert file_api.age_at_exam("15/03/2002", 20194) == 17.0
