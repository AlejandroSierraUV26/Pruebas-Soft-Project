"""Pruebas de carga del archivo: errores, codificacion y filas defectuosas."""
from __future__ import annotations

import pytest

import file_api
from conftest import HEADERS, make_row


def _write_dataset(path, rows, headers=HEADERS, newline="\n", bom=False):
    lines = ["\t".join(headers)]
    lines += ["\t".join(row) for row in rows]
    content = ("\ufeff" if bom else "") + newline.join(lines) + newline
    path.write_bytes(content.encode("utf-8"))


def _load(tmp_path, monkeypatch, rows, **kwargs):
    dataset = tmp_path / "icfes_data.csv"
    _write_dataset(dataset, rows, **kwargs)
    monkeypatch.setattr(file_api, "DATASET_PATH", dataset)
    file_api.load_dataset()
    return dataset


def test_archivo_vacio_reporta_error(tmp_path, monkeypatch, fresh_state):
    dataset = tmp_path / "vacio.csv"
    dataset.write_bytes(b"")
    monkeypatch.setattr(file_api, "DATASET_PATH", dataset)

    file_api.load_dataset()

    assert file_api.LOAD_STATE["status"] == "error"


def test_columna_requerida_ausente_reporta_error(tmp_path, monkeypatch, fresh_state):
    headers = [column for column in HEADERS if column != "PUNT_GLOBAL"]
    _load(tmp_path, monkeypatch, [], headers=headers)

    assert file_api.LOAD_STATE["status"] == "error"


def test_bom_y_saltos_crlf_se_cargan(tmp_path, monkeypatch, fresh_state):
    _load(tmp_path, monkeypatch, [make_row(ESTU_CONSECUTIVO="BOM-1")], newline="\r\n", bom=True)

    assert file_api.LOAD_STATE["status"] == "ready"
    assert file_api.LOAD_STATE["rows_loaded"] == 1
    assert file_api.DATASET_CACHE.record_at(0)["student_code"] == "BOM-1"


def test_utf8_invalido_reporta_error(tmp_path, monkeypatch, fresh_state):
    dataset = tmp_path / "invalido.csv"
    dataset.write_bytes(b"\xff\xfe\x00\x00")
    monkeypatch.setattr(file_api, "DATASET_PATH", dataset)

    file_api.load_dataset()

    assert file_api.LOAD_STATE["status"] == "error"


def test_lineas_vacias_y_truncadas_se_descartan(tmp_path, monkeypatch, fresh_state):
    rows = [make_row(ESTU_CONSECUTIVO="S0"), make_row(ESTU_CONSECUTIVO="S1"), [], make_row()[:5]]
    _load(tmp_path, monkeypatch, rows)

    assert file_api.LOAD_STATE["status"] == "ready"
    assert file_api.LOAD_STATE["rows_loaded"] == 2
    assert [file_api.DATASET_CACHE.record_at(i)["student_code"] for i in range(2)] == ["S0", "S1"]


def test_progreso_refleja_el_archivo_completo(tmp_path, monkeypatch, fresh_state):
    dataset = _load(tmp_path, monkeypatch, [make_row(ESTU_CONSECUTIVO="S0"), make_row(ESTU_CONSECUTIVO="S1")])

    assert file_api.LOAD_STATE["bytes_read"] == file_api.LOAD_STATE["file_size"] == dataset.stat().st_size
    assert file_api.LOAD_STATE["rows_loaded"] == 2
    assert file_api.LOAD_STATE["error"] is None


@pytest.mark.parametrize("payload", [b"\x00\x01\x02", b"\t\t\t\n"])
def test_archivos_sin_encabezado_valido_reportan_error(tmp_path, monkeypatch, fresh_state, payload):
    dataset = tmp_path / "raro.csv"
    dataset.write_bytes(payload)
    monkeypatch.setattr(file_api, "DATASET_PATH", dataset)

    file_api.load_dataset()

    assert file_api.LOAD_STATE["status"] == "error"
