"""Run from the repository root: python -m practice.pz04.experiment."""

import asyncio
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor
import json
import os
from pathlib import Path
import platform
import sqlite3
from statistics import median
from tempfile import TemporaryDirectory
from threading import Barrier, Lock
from time import perf_counter

from src.core.bus import InMemoryBus
from src.core.deadband import DeadbandFilter
from src.core.models import Quality, Tag
from src.storage.database import Database
from src.storage.service import StorageService


# Per-tag order is preserved in every version. Tags have independent histories.
def filter_trace(values):
    filter_ = DeadbandFilter(0.5)
    return tuple(i for i, value in enumerate(values)
                 if filter_.should_store(Tag("TEMP_01", value, i, Quality.GOOD)))


def cpu_experiment(workers):
    traces = [tuple(20 + ((i * 13 + tag) % 41) / 10 for i in range(8_000))
              for tag in range(96)]
    sequential = lambda: tuple(map(filter_trace, traces))
    return series([
        ("sequential", sequential),
        *((f"p={p}", lambda p=p: parallel(traces, p)) for p in workers),
    ])


def parallel(traces, workers):
    with ProcessPoolExecutor(max_workers=workers) as pool:
        return tuple(pool.map(filter_trace, traces, chunksize=1))


def history(path, tag):
    connection = sqlite3.connect(path)
    try:
        return Database._fetch_history(connection, tag, 256)
    finally:
        connection.close()


async def concurrent_history(path, tags, workers):
    loop = asyncio.get_running_loop()
    with ThreadPoolExecutor(max_workers=workers) as pool:
        return await asyncio.gather(
            *(loop.run_in_executor(pool, history, path, tag) for tag in tags)
        )


def io_experiment(path):
    tags = [f"T{i:02}" for i in range(48)]
    connection = sqlite3.connect(path)
    try:
        connection.executescript("""
            CREATE TABLE tag_history (id INTEGER PRIMARY KEY, tag_id TEXT,
                value REAL, timestamp REAL, quality TEXT);
            CREATE INDEX idx ON tag_history(tag_id, timestamp DESC, id DESC);
        """)
        connection.executemany(
            "INSERT INTO tag_history(tag_id,value,timestamp,quality) VALUES (?,?,?,'GOOD')",
            ((tag, i / 2, i) for tag in tags for i in range(256)),
        )
        connection.commit()
    finally:
        connection.close()
    return series([
        ("sync", lambda: [history(path, tag) for tag in tags]),
        *((f"p={p}", lambda p=p: asyncio.run(concurrent_history(path, tags, p)))
          for p in (2, 4, 8)),
    ])


def shared_state(pool, synchronized):
    # Model two attempts to claim the same archival transition.
    state = {}
    accepted = []
    rendezvous = Barrier(2)
    lock = Lock()
    key = ("TEMP_01", 20.5)

    def claim():
        missing = key not in state
        rendezvous.wait(timeout=5)
        if synchronized:
            with lock:
                if key not in state:
                    state[key] = True
                    accepted.append(key)
        elif missing:
            state[key] = True
            accepted.append(key)

    futures = [pool.submit(claim) for _ in range(2)]
    for future in futures:
        future.result()
    return len(accepted) != len(state)


def race_experiment():
    with ThreadPoolExecutor(max_workers=2) as pool:
        def trials(synchronized):
            return sum(shared_state(pool, synchronized) for _ in range(100))

        evidence = series([
            ("without_lock", lambda: trials(False)),
            ("with_lock", lambda: trials(True)),
        ], equal=False)
        assert evidence["without_lock"]["result"] == 100
        assert evidence["with_lock"]["result"] == 0
        return evidence


async def archive(path, threshold):
    database = Database(str(path))
    tags = [Tag("TEMP_01", value, i, Quality.GOOD)
            for i, value in enumerate((20.0, 20.2, 20.5) * 60)]
    service = StorageService(
        bus=InMemoryBus(), deadband=DeadbandFilter(threshold), database=database
    )
    async with database:
        start = perf_counter()
        for tag in tags:
            await service.process_tag(tag)
        elapsed = perf_counter() - start
        stored = await database.get_history("TEMP_01", limit=len(tags))
    return elapsed, len(stored)


def threshold_experiment(directory):
    run = 0

    def sample(threshold):
        nonlocal run
        run += 1
        return asyncio.run(archive(directory / f"archive-{run}.db", threshold))

    return series([
        ("threshold_0.5", lambda: sample(0.5)),
        ("threshold_0.75", lambda: sample(0.75)),
    ], equal=False, internal_timer=True)


def series(variants, *, equal=True, internal_timer=False):
    rows = {name: {"warmup_s": [], "samples_s": [], "results": []} for name, _ in variants}
    reference = None
    for _ in range(7):
        for name, function in variants:
            start = perf_counter()
            result = function()
            elapsed = perf_counter() - start
            if internal_timer:
                elapsed, result = result
            if reference is None:
                reference = result
            if equal and result != reference:
                raise AssertionError(f"{name}: different output")
            row = rows[name]
            if len(row["warmup_s"]) < 2:
                row["warmup_s"].append(elapsed)
            else:
                row["samples_s"].append(elapsed)
                row["results"].append(result if isinstance(result, int) else len(result))
    for row in rows.values():
        values = row["samples_s"]
        assert len(set(row["results"])) == 1
        row.update(min_s=min(values), median_s=median(values), max_s=max(values),
                   spread=(max(values) - min(values)) / median(values),
                   result=row["results"][0])
    return rows


def main():
    logical = os.cpu_count()
    if logical is None or logical < 3:
        raise RuntimeError("At least three distinct worker counts are required")
    with TemporaryDirectory(prefix="mini-scada-pz04-") as temp:
        directory = Path(temp)
        result = {
            "platform": platform.platform(), "python": platform.python_version(),
            "sqlite": sqlite3.sqlite_version, "logical": logical,
            "cpu": cpu_experiment(sorted({1, 2, 4, logical})),
            "io": io_experiment(directory / "history.db"),
            "race": race_experiment(),
            "threshold": threshold_experiment(directory),
        }
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
