"""PLS-01 · Depuración y conversión de registros (clean_value / clean_record).

Regla de negocio (Entrega 2, §7.7.2): se descartan filas sin código de
estudiante, periodo o departamento, con periodo no numérico o sin puntaje
global; el resto se limpia (espacios -> recortados, vacíos -> None) y los
puntajes se convierten a número. Semántica esperada: un puntaje fuera de la
escala oficial del ICFES (global 0-500, áreas 0-100) no es un dato válido.
"""
import pytest

import file_api
from conftest import make_row


def test_recorta_espacios_y_vacios_a_none(positions):
    record = file_api.clean_record(make_row(ESTU_DEPTO_RESIDE="  VALLE  ", COLE_BILINGUE="   "), positions)
    assert record["department"] == "VALLE"
    assert record["school_bilingual"] is None


@pytest.mark.parametrize("column", ["ESTU_CONSECUTIVO", "PERIODO", "ESTU_DEPTO_RESIDE", "PUNT_GLOBAL"])
def test_descarta_filas_sin_campos_esenciales(positions, column):
    assert file_api.clean_record(make_row(**{column: ""}), positions) is None


def test_normaliza_periodo_y_convierte_puntajes(positions):
    record = file_api.clean_record(make_row(PERIODO="20194.0", PUNT_GLOBAL="260"), positions)
    assert record["period"] == "20194"
    assert record["score_global"] == 260.0 and isinstance(record["score_global"], float)
    assert "birth_date" not in record and record["age"] == 17.0


def test_descarta_periodo_no_numerico(positions):
    assert file_api.clean_record(make_row(PERIODO="2019-2"), positions) is None


def test_fila_truncada_no_rompe_la_lectura(positions):
    truncated = make_row()[: positions["score_reading"]]
    assert file_api.clean_record(truncated, positions) is None


def test_area_vacia_se_conserva_como_ausente(positions):
    record = file_api.clean_record(make_row(PUNT_INGLES=""), positions)
    assert record is not None and record["score_english"] is None


@pytest.mark.parametrize("column,value", [
    ("PUNT_GLOBAL", "-5"),       # negativo: imposible en la escala ICFES
    ("PUNT_GLOBAL", "650"),      # por encima del máximo (500)
    ("PUNT_MATEMATICAS", "180"), # área por encima de 100
])
def test_semantica_rechaza_puntajes_fuera_de_escala(positions, column, value):
    """Esperado: el registro se descarta (None). Un puntaje fuera de escala no
    debe entrar a la caché ni a los promedios."""
    record = file_api.clean_record(make_row(**{column: value}), positions)
    assert record is None, f"{column}={value} fue aceptado como válido"
