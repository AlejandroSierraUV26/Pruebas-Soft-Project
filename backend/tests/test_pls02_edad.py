"""PLS-02 · Cálculo de la edad al presentar el examen (age_at_exam).

Regla (Entrega 2, §7.7.2, paso 4): se calcula la edad al presentar el examen
a partir de la fecha de nacimiento (dd/mm/aaaa) y el periodo (AAAAS), y se
descartan edades fuera del rango 10-90. Semántica: "edad" significa años
cumplidos en la fecha del examen. El periodo 20194 corresponde a la
aplicación del calendario A del segundo semestre (agosto de 2019).
"""
import pytest

import file_api


def test_caso_tipico():
    assert file_api.age_at_exam("15/03/2002", 20194) == 17.0


@pytest.mark.parametrize("birth,expected", [
    ("01/01/2009", 10.0),   # límite inferior válido
    ("01/01/2010", None),   # 9 años -> fuera de rango
    ("01/01/1929", 90.0),   # límite superior válido
    ("01/01/1928", None),   # 91 años -> fuera de rango
])
def test_valores_limite(birth, expected):
    assert file_api.age_at_exam(birth, 20194) == expected


@pytest.mark.parametrize("birth", [None, "", "sin dato", "2002-03-15", "15/03/02"])
def test_formatos_invalidos_devuelven_none(birth):
    assert file_api.age_at_exam(birth, 20194) is None


def test_semantica_anos_cumplidos_a_la_fecha_del_examen():
    """Nacido el 20/12/2001 y evaluado en agosto de 2019: tiene 17 años
    cumplidos (los 18 los cumple en diciembre)."""
    age = file_api.age_at_exam("20/12/2001", 20194)
    assert age == 17.0, f"edad calculada={age}, esperada=17.0"
