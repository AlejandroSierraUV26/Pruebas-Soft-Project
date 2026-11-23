"""Pruebas HTTP de los endpoints con FastAPI TestClient.

Las pruebas unitarias llaman las funciones directamente; estas validan el
contrato real de la API: codigos de estado, validacion de parametros,
encabezados CORS y forma de las respuestas.
"""
from __future__ import annotations

import pytest

import file_api
from conftest import build_cache, install_cache, make_row

try:  # conftest registra un sustituto de FastAPI cuando no esta instalado.
    from fastapi.testclient import TestClient
except ModuleNotFoundError:  # pragma: no cover - depende del entorno
    TestClient = None

pytestmark = pytest.mark.skipif(TestClient is None, reason="FastAPI/httpx no estan instalados")


@pytest.fixture
def client():
    with TestClient(file_api.app) as test_client:
        yield test_client


def test_health_responde_ok(client):
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "dataset": file_api.DATASET_PATH.name}


def test_cors_permite_el_frontend_local(client):
    response = client.get("/api/health", headers={"Origin": "http://localhost:5173"})
    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://localhost:5173"


def test_load_status_expone_el_progreso(client, positions, fresh_state):
    install_cache(build_cache([make_row()], positions))
    response = client.get("/api/load-status")
    assert response.status_code == 200
    body = response.json()
    assert {"status", "bytes_read", "file_size", "rows_loaded", "error", "percent"} <= body.keys()


def test_records_responde_202_mientras_carga(client, monkeypatch, fresh_state):
    monkeypatch.setattr(file_api, "active_cache", lambda: None)
    monkeypatch.setattr(file_api, "start_loading", lambda: None)
    monkeypatch.setattr(
        file_api,
        "load_status",
        lambda: {"status": "loading", "bytes_read": 10, "file_size": 100, "rows_loaded": 0, "error": None, "percent": 10.0},
    )
    response = client.get("/api/records")
    assert response.status_code == 202
    assert response.json()["status"] == "loading"


def test_records_devuelve_el_contrato_cuando_la_cache_esta_lista(client, positions, fresh_state):
    install_cache(build_cache([make_row()], positions))
    response = client.get("/api/records")
    assert response.status_code == 200
    body = response.json()
    assert (body["total_records"], body["filtered_records"], body["page"], body["page_size"]) == (1, 1, 1, 20)
    record = body["records"][0]
    assert record["student_code"] == "SB11201940000001"
    assert record["period"] == "20194"
    assert record["score_global"] == 260
    assert body["filters"]["period"] == ["20194"]
    assert body["filters"]["department"] == ["VALLE"]


def test_records_responde_503_si_no_existe_el_archivo(client, tmp_path, monkeypatch, fresh_state):
    monkeypatch.setattr(file_api, "DATASET_PATH", tmp_path / "no_existe.csv")
    response = client.get("/api/records")
    assert response.status_code == 503


@pytest.mark.parametrize("params", [{"page": 0}, {"page_size": 0}, {"page_size": 101}, {"page": "x"}])
def test_records_valida_la_paginacion(client, params):
    response = client.get("/api/records", params=params)
    assert response.status_code == 422


def test_stats_devuelve_promedios(client, positions, fresh_state):
    install_cache(build_cache([make_row()], positions))
    response = client.get("/api/stats", params={"group_by": "period"})
    assert response.status_code == 200
    body = response.json()
    assert body["group_by"] == "period"
    assert body["overall_average_global"] == 260.0
    assert body["groups"][0]["count"] == 1


@pytest.mark.parametrize("group_by", ["internet", "score_global", ""])
def test_stats_rechaza_group_by_invalido(client, group_by):
    response = client.get("/api/stats", params={"group_by": group_by})
    assert response.status_code == 422
