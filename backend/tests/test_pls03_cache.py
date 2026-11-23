"""PLS-03 · Codificación compacta en memoria y carga del archivo
(DatasetCache.add / record_at / load_dataset).

Invariante: lo que se guarda en la caché (categorías como enteros, puntajes
como enteros de 16 bits con -1 = ausente) debe reconstruirse igual con
record_at. Regla de carga: las filas inválidas se descartan sin detener la
carga del resto del archivo (Entrega 2, §7.7.2-7.7.3).
"""
import file_api
from conftest import HEADERS, build_cache, make_row


def test_ida_y_vuelta_conserva_el_registro(positions):
    raw = make_row(ESTU_CONSECUTIVO="SB11-ÑANDÚ-7")
    cache = build_cache([raw], positions)
    original = file_api.clean_record(raw, positions)
    rebuilt = cache.record_at(0)
    for name in file_api.CATEGORY_FIELDS:
        assert rebuilt[name] == original[name]
    for name in file_api.SCORE_FIELDS:
        assert rebuilt[name] == original[name]
    assert rebuilt["student_code"] == "SB11-ÑANDÚ-7"


def test_identificadores_de_distinto_largo_no_se_mezclan(positions):
    codes = ["A", "SB11201940000002", "ÁÉ", "X" * 40]
    cache = build_cache([make_row(ESTU_CONSECUTIVO=c) for c in codes], positions)
    assert [cache.record_at(i)["student_code"] for i in range(len(cache))] == codes


def test_ausentes_y_cero_se_distinguen(positions):
    cache = build_cache([make_row(PUNT_INGLES="", PUNT_MATEMATICAS="0", FAMI_ESTRATOVIVIENDA="")], positions)
    record = cache.record_at(0)
    assert record["score_english"] is None
    assert record["score_math"] == 0
    assert record["stratum"] is None


def test_diccionario_de_categorias_sin_duplicados(positions):
    rows = [make_row(ESTU_DEPTO_RESIDE=d) for d in ["VALLE", "CAUCA", "VALLE", "VALLE"]]
    cache = build_cache(rows, positions)
    assert cache.category_values["department"] == [None, "VALLE", "CAUCA"]
    assert list(cache.category_codes["department"]) == [1, 2, 1, 1]


def _write_tsv(path, rows):
    lines = ["\t".join(HEADERS)] + ["\t".join(r) for r in rows]
    path.write_text("﻿" + "\n".join(lines) + "\n", encoding="utf-8")


def test_carga_completa_descarta_filas_invalidas(tmp_path, monkeypatch, fresh_state):
    dataset = tmp_path / "icfes_data.csv"
    _write_tsv(dataset, [make_row(ESTU_CONSECUTIVO=f"S{i}") for i in range(5)] + [make_row(PERIODO="")])
    monkeypatch.setattr(file_api, "DATASET_PATH", dataset)
    file_api.load_dataset()
    assert file_api.LOAD_STATE["status"] == "ready"
    assert file_api.LOAD_STATE["rows_loaded"] == 5


def test_semantica_una_fila_corrupta_no_aborta_la_carga(tmp_path, monkeypatch, fresh_state):
    """Esperado: 5 filas válidas cargadas y la corrupta descartada.
    PUNT_GLOBAL=40000 no cabe en un entero de 16 bits."""
    dataset = tmp_path / "icfes_data.csv"
    rows = [make_row(ESTU_CONSECUTIVO=f"S{i}") for i in range(5)]
    rows.insert(2, make_row(ESTU_CONSECUTIVO="CORRUPTA", PUNT_GLOBAL="40000"))
    _write_tsv(dataset, rows)
    monkeypatch.setattr(file_api, "DATASET_PATH", dataset)
    file_api.load_dataset()
    state = file_api.LOAD_STATE
    assert state["status"] == "ready", f"status={state['status']!r}, error={state['error']!r}, caché={file_api.DATASET_CACHE}"
    assert state["rows_loaded"] == 5
