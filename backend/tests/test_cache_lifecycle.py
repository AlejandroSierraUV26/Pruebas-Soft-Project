"""Pruebas del ciclo de vida de la cache y del cargador en segundo plano."""
from __future__ import annotations

import time
from array import array

import file_api
from conftest import HEADERS, build_cache, install_cache, make_row


def _write_tsv(path, rows):
    lines = ["\t".join(HEADERS)] + ["\t".join(row) for row in rows]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def test_active_cache_expira_tras_el_ttl(positions, fresh_state):
    install_cache(build_cache([make_row()], positions))
    file_api.LAST_ACCESS = time.monotonic() - file_api.CACHE_TTL_SECONDS - 1
    file_api.FILTER_CACHE_KEY = ("20194",)
    file_api.FILTER_CACHE_INDICES = array("I", [0])
    file_api.STATS_CACHE = {"period": {"grupos": []}}

    assert file_api.active_cache() is None
    assert file_api.DATASET_CACHE is None
    assert file_api.FILTER_CACHE_KEY is None and file_api.FILTER_CACHE_INDICES is None
    assert file_api.STATS_CACHE == {}
    assert file_api.LOAD_STATE["status"] == "idle"


def test_active_cache_renueva_el_ultimo_acceso(positions, fresh_state):
    install_cache(build_cache([make_row()], positions))
    previous = time.monotonic() - 10
    file_api.LAST_ACCESS = previous

    cache = file_api.active_cache()

    assert cache is file_api.DATASET_CACHE
    assert file_api.LAST_ACCESS > previous


def test_load_dataset_invalida_las_caches_derivadas(tmp_path, monkeypatch, fresh_state):
    dataset = tmp_path / "icfes_data.csv"
    _write_tsv(dataset, [make_row()])
    monkeypatch.setattr(file_api, "DATASET_PATH", dataset)
    file_api.FILTER_CACHE_KEY = ("20194",)
    file_api.FILTER_CACHE_INDICES = array("I", [0])
    file_api.STATS_CACHE = {"period": {"grupos": []}}

    file_api.load_dataset()

    assert file_api.LOAD_STATE["status"] == "ready"
    assert file_api.FILTER_CACHE_KEY is None and file_api.FILTER_CACHE_INDICES is None
    assert file_api.STATS_CACHE == {}


def test_start_loading_inicia_un_solo_hilo(tmp_path, monkeypatch, fresh_state):
    dataset = tmp_path / "icfes_data.csv"
    _write_tsv(dataset, [make_row()])
    monkeypatch.setattr(file_api, "DATASET_PATH", dataset)
    file_api.LOAD_STATE["status"] = "idle"

    class FakeThread:
        created = []

        def __init__(self, target=None, daemon=None):
            self.target = target
            self.daemon = daemon
            self.started = False
            FakeThread.created.append(self)

        def start(self):
            self.started = True

    monkeypatch.setattr(file_api.threading, "Thread", FakeThread)
    file_api.start_loading()
    file_api.start_loading()

    assert len(FakeThread.created) == 1
    assert FakeThread.created[0].started is True
    assert FakeThread.created[0].daemon is True
    assert file_api.LOAD_STATE["status"] == "loading"
    assert file_api.LOAD_STATE["file_size"] == dataset.stat().st_size
