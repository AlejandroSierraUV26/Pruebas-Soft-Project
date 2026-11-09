from __future__ import annotations

import csv
import math
import os
import threading
import time
from array import array
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

BASE_DIR = Path(__file__).resolve().parent
DATASET_PATH = Path(os.environ.get("ICFES_DATASET", BASE_DIR.parent / "icfes_data.csv"))

FIELDS = {
    "student_code": "ESTU_CONSECUTIVO",
    "gender": "ESTU_GENERO",
    "birth_date": "ESTU_FECHANACIMIENTO",
    "period": "PERIODO",
    "department": "ESTU_DEPTO_RESIDE",
    "municipality": "ESTU_MCPIO_RESIDE",
    "stratum": "FAMI_ESTRATOVIVIENDA",
    "nse": "ESTU_NSE_INDIVIDUAL",
    "mother_education": "FAMI_EDUCACIONMADRE",
    "father_education": "FAMI_EDUCACIONPADRE",
    "internet": "FAMI_TIENEINTERNET",
    "computer": "FAMI_TIENECOMPUTADOR",
    "school_name": "COLE_NOMBRE_ESTABLECIMIENTO",
    "school_nature": "COLE_NATURALEZA",
    "school_area": "COLE_AREA_UBICACION",
    "school_schedule": "COLE_JORNADA",
    "school_calendar": "COLE_CALENDARIO",
    "school_bilingual": "COLE_BILINGUE",
    "score_reading": "PUNT_LECTURA_CRITICA",
    "score_math": "PUNT_MATEMATICAS",
    "score_science": "PUNT_C_NATURALES",
    "score_social": "PUNT_SOCIALES_CIUDADANAS",
    "score_english": "PUNT_INGLES",
    "score_global": "PUNT_GLOBAL",
    "percentile_global": "PERCENTIL_GLOBAL",
    "english_level": "DESEMP_INGLES",
}
FILTER_FIELDS = ("period", "gender", "department", "stratum", "school_nature", "school_area", "school_schedule")
CATEGORY_FIELDS = (
    "period", "gender", "department", "municipality", "stratum", "nse", "mother_education", "father_education",
    "internet", "computer", "school_name", "school_nature", "school_area", "school_schedule", "school_calendar",
    "school_bilingual", "english_level",
)
SCORE_FIELDS = (
    "score_reading", "score_math", "score_science", "score_social", "score_english", "score_global", "percentile_global",
)
NUMERIC_FIELDS = ("age", *SCORE_FIELDS)
WIDE_CATEGORIES = ("school_name",)
CACHE_TTL_SECONDS = 900

app = FastAPI(title="Explorador ICFES", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["GET"],
    allow_headers=["*"],
)


def clean_value(value: str | None) -> str | None:
    value = (value or "").strip()
    return value or None


def age_at_exam(birth_date: str | None, period: int) -> float | None:
    try:
        age = period // 10 - int((birth_date or "").split("/")[-1])
    except ValueError:
        return None
    return float(age) if 10 <= age <= 90 else None


def clean_record(raw: list[str], positions: dict[str, int]) -> dict[str, Any] | None:
    record = {
        name: clean_value(raw[index] if index < len(raw) else "")
        for name, index in positions.items()
    }
    if not record["student_code"] or not record["period"] or not record["department"]:
        return None
    try:
        period = int(float(record["period"]))
        record["period"] = str(period)
        record["age"] = age_at_exam(record.pop("birth_date"), period)
        for name in SCORE_FIELDS:
            record[name] = float(record[name]) if record[name] is not None else None
    except ValueError:
        return None
    if record["score_global"] is None:
        return None
    return record


class DatasetCache:
    def __init__(self) -> None:
        self.identifiers = bytearray()
        self.identifier_offsets = array("I")
        self.category_values = {name: [None] for name in CATEGORY_FIELDS}
        self.category_lookup = {name: {} for name in CATEGORY_FIELDS}
        self.category_codes = {name: array("I" if name in WIDE_CATEGORIES else "H") for name in CATEGORY_FIELDS}
        # Enteros de 16 bits; -1 marca un valor ausente.
        self.scores = {name: array("h") for name in NUMERIC_FIELDS}

    def add(self, record: dict[str, Any]) -> None:
        self.identifier_offsets.append(len(self.identifiers))
        self.identifiers.extend(record["student_code"].encode("utf-8"))
        for name in CATEGORY_FIELDS:
            value = record[name]
            lookup = self.category_lookup[name]
            if value is None:
                code = 0
            else:
                code = lookup.get(value)
                if code is None:
                    code = len(self.category_values[name])
                    lookup[value] = code
                    self.category_values[name].append(value)
            self.category_codes[name].append(code)
        for name in NUMERIC_FIELDS:
            value = record[name]
            self.scores[name].append(int(round(value)) if value is not None else -1)

    def __len__(self) -> int:
        return len(self.identifier_offsets)

    def record_at(self, index: int) -> dict[str, Any]:
        start = self.identifier_offsets[index]
        end = self.identifier_offsets[index + 1] if index + 1 < len(self) else len(self.identifiers)
        record = {"student_code": self.identifiers[start:end].decode("utf-8")}
        for name in CATEGORY_FIELDS:
            code = self.category_codes[name][index]
            record[name] = self.category_values[name][code]
        for name in NUMERIC_FIELDS:
            value = self.scores[name][index]
            record[name] = None if value < 0 else value
        return record


STATE_LOCK = threading.Lock()
DATASET_CACHE: DatasetCache | None = None
LAST_ACCESS = 0.0
FILTER_CACHE_KEY: tuple[str | None, ...] | None = None
FILTER_CACHE_INDICES: array | None = None
STATS_CACHE: dict[str, dict[str, Any]] = {}
LOAD_STATE = {"status": "idle", "bytes_read": 0, "file_size": 0, "rows_loaded": 0, "error": None}


def read_progress_lines(source):
    bytes_read = 0
    line_count = 0
    for raw_line in source:
        bytes_read += len(raw_line)
        line_count += 1
        if line_count % 4096 == 0:
            with STATE_LOCK:
                LOAD_STATE["bytes_read"] = bytes_read
        yield raw_line.decode("utf-8-sig" if line_count == 1 else "utf-8")
    with STATE_LOCK:
        LOAD_STATE["bytes_read"] = bytes_read


def load_dataset() -> None:
    global DATASET_CACHE, LAST_ACCESS, FILTER_CACHE_KEY, FILTER_CACHE_INDICES, STATS_CACHE
    try:
        file_size = DATASET_PATH.stat().st_size
        cache = DatasetCache()
        with DATASET_PATH.open("rb") as source:
            reader = csv.reader(read_progress_lines(source), delimiter="\t")
            headers = next(reader)
            positions = {name: headers.index(column) for name, column in FIELDS.items()}
            for raw in reader:
                record = clean_record(raw, positions)
                if record:
                    cache.add(record)
                    if len(cache) % 10_000 == 0:
                        with STATE_LOCK:
                            LOAD_STATE["rows_loaded"] = len(cache)
        with STATE_LOCK:
            DATASET_CACHE = cache
            LAST_ACCESS = time.monotonic()
            FILTER_CACHE_KEY = None
            FILTER_CACHE_INDICES = None
            STATS_CACHE = {}
            LOAD_STATE.update(status="ready", bytes_read=file_size, file_size=file_size, rows_loaded=len(cache), error=None)
    except (FileNotFoundError, OSError, ValueError, StopIteration, csv.Error, OverflowError, MemoryError) as error:
        with STATE_LOCK:
            LOAD_STATE.update(status="error", error=str(error))


def active_cache() -> DatasetCache | None:
    global DATASET_CACHE, LAST_ACCESS, FILTER_CACHE_KEY, FILTER_CACHE_INDICES, STATS_CACHE, LOAD_STATE
    with STATE_LOCK:
        if DATASET_CACHE is not None and time.monotonic() - LAST_ACCESS > CACHE_TTL_SECONDS:
            DATASET_CACHE = None
            FILTER_CACHE_KEY = None
            FILTER_CACHE_INDICES = None
            STATS_CACHE = {}
            LOAD_STATE = {"status": "idle", "bytes_read": 0, "file_size": 0, "rows_loaded": 0, "error": None}
        if DATASET_CACHE is not None:
            LAST_ACCESS = time.monotonic()
        return DATASET_CACHE


def start_loading() -> None:
    with STATE_LOCK:
        if DATASET_CACHE is not None or LOAD_STATE["status"] == "loading":
            return
        try:
            file_size = DATASET_PATH.stat().st_size
        except OSError as error:
            LOAD_STATE.update(status="error", error=str(error))
            return
        LOAD_STATE.update(status="loading", bytes_read=0, file_size=file_size, rows_loaded=0, error=None)
        threading.Thread(target=load_dataset, daemon=True).start()


def load_status() -> dict[str, Any]:
    active_cache()
    with STATE_LOCK:
        file_size = LOAD_STATE["file_size"]
        percent = 100 if LOAD_STATE["status"] == "ready" else round(LOAD_STATE["bytes_read"] * 100 / file_size, 1) if file_size else 0
        return {**LOAD_STATE, "percent": percent}


def matching_indices(cache: DatasetCache, filters: dict[str, str | None]) -> array:
    global FILTER_CACHE_KEY, FILTER_CACHE_INDICES
    key = tuple(filters[name] for name in FILTER_FIELDS)
    with STATE_LOCK:
        if FILTER_CACHE_KEY == key and FILTER_CACHE_INDICES is not None:
            return FILTER_CACHE_INDICES

    wanted_codes = {}
    for name, value in filters.items():
        if value:
            code = cache.category_lookup[name].get(value)
            if code is None:
                return array("I")
            wanted_codes[name] = code

    matches = array("I")
    for index in range(len(cache)):
        if all(cache.category_codes[name][index] == code for name, code in wanted_codes.items()):
            matches.append(index)

    with STATE_LOCK:
        FILTER_CACHE_KEY = key
        FILTER_CACHE_INDICES = matches
    return matches


@app.get("/api/records")
def records(
    period: str | None = None,
    gender: str | None = None,
    department: str | None = None,
    stratum: str | None = None,
    school_nature: str | None = None,
    school_area: str | None = None,
    school_schedule: str | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
) -> Any:
    filters = {
        "period": period,
        "gender": gender,
        "department": department,
        "stratum": stratum,
        "school_nature": school_nature,
        "school_area": school_area,
        "school_schedule": school_schedule,
    }
    cache = active_cache()
    if cache is None:
        start_loading()
        state = load_status()
        if state["status"] == "error":
            raise HTTPException(status_code=503, detail=state["error"])
        return JSONResponse(status_code=202, content=state)

    matches = matching_indices(cache, filters)
    offset = (page - 1) * page_size
    result = [cache.record_at(index) for index in matches[offset:offset + page_size]]

    return {
        "total_records": len(cache),
        "filtered_records": len(matches),
        "page": page,
        "page_size": page_size,
        "records": result,
        "filters": {name: sorted(value for value in cache.category_values[name][1:] if value is not None) for name in FILTER_FIELDS},
    }


GROUPABLE_FIELDS = ("period", "gender", "department", "municipality", "stratum", "mother_education", "father_education", "school_nature", "school_area", "school_schedule")


@app.get("/api/stats")
def stats(group_by: str = Query("period")) -> Any:
    if group_by not in GROUPABLE_FIELDS:
        raise HTTPException(status_code=422, detail=f"group_by debe ser uno de: {', '.join(GROUPABLE_FIELDS)}")
    cache = active_cache()
    if cache is None:
        start_loading()
        state = load_status()
        if state["status"] == "error":
            raise HTTPException(status_code=503, detail=state["error"])
        return JSONResponse(status_code=202, content=state)

    with STATE_LOCK:
        cached = STATS_CACHE.get(group_by)
    if cached is not None:
        return cached

    groups: dict[int, dict[str, Any]] = {}
    codes = cache.category_codes[group_by]
    score_arrays = {name: cache.scores[name] for name in SCORE_FIELDS}
    for index in range(len(cache)):
        code = codes[index]
        bucket = groups.get(code)
        if bucket is None:
            bucket = {"count": 0, "sums": {name: 0 for name in SCORE_FIELDS}, "present": {name: 0 for name in SCORE_FIELDS}}
            groups[code] = bucket
        bucket["count"] += 1
        for name, values in score_arrays.items():
            value = values[index]
            if value >= 0:
                bucket["sums"][name] += value
                bucket["present"][name] += 1

    overall_count = len(cache)
    overall_global = [bucket["sums"]["score_global"] for bucket in groups.values()]
    overall_present = [bucket["present"]["score_global"] for bucket in groups.values()]
    overall_avg = sum(overall_global) / sum(overall_present) if sum(overall_present) else None

    result = []
    for code, bucket in groups.items():
        label = cache.category_values[group_by][code]
        averages = {
            name: round(bucket["sums"][name] / bucket["present"][name], 1) if bucket["present"][name] else None
            for name in SCORE_FIELDS
        }
        result.append({
            "value": label,
            "count": bucket["count"],
            "share": round(bucket["count"] * 100 / overall_count, 2) if overall_count else 0,
            "averages": averages,
            "diff_global": round(averages["score_global"] - overall_avg, 1) if averages["score_global"] is not None and overall_avg is not None else None,
        })
    result.sort(key=lambda item: (item["averages"]["score_global"] is None, -(item["averages"]["score_global"] or 0)))
    payload = {
        "group_by": group_by,
        "total_records": overall_count,
        "overall_average_global": round(overall_avg, 1) if overall_avg is not None else None,
        "groups": result,
    }
    with STATE_LOCK:
        STATS_CACHE[group_by] = payload
    return payload


@app.get("/api/load-status")
def get_load_status() -> dict[str, Any]:
    return load_status()


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok", "dataset": DATASET_PATH.name}
