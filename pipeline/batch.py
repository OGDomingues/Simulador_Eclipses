import os
from concurrent.futures import ProcessPoolExecutor, as_completed

from skyfield.api import load, load_file

from core import (
    is_possible_eclipse,
    refine_maximum,
    compute_contacts,
)
from infrastructure.config import EPHEMERIS_PATH
_TS = None
_EPH = None


def _get_context():
    global _TS, _EPH

    if _TS is None:
        _TS = load.timescale()

    if _EPH is None:
        _EPH = load_file(
            str(EPHEMERIS_PATH)
        )

    return _EPH, _TS
def _process_one(t_nm):
    eph, ts = _get_context()

    if not is_possible_eclipse(
            eph,
            ts,
            t_nm
    ):
        return None

    t_max = refine_maximum(
        eph,
        ts,
        t_nm
    )

    C1, C2, MAX, C3, C4 = compute_contacts(
        eph,
        ts,
        t_max
    )

    if C1 is None or C4 is None:
        return None

    return {
        "date": MAX.utc_strftime("%d-%m-%Y"),
        "C1": C1,
        "C2": C2,
        "MAX": MAX,
        "C3": C3,
        "C4": C4,
    }
def run_batch(
        new_moon_times,
        max_workers=None,
):
    if max_workers is None:
        configured_workers = os.getenv("ECLIPSE_MAX_WORKERS")
        if configured_workers:
            max_workers = int(configured_workers)
        else:
            max_workers = min(os.cpu_count() or 1, 4)

    max_workers = max(
        1,
        min(max_workers, len(new_moon_times)),
    )

    results = []

    with ProcessPoolExecutor(
            max_workers=max_workers
    ) as executor:

        futures = [
            executor.submit(
                _process_one,
                t
            )
            for t in new_moon_times
        ]

        for future in as_completed(futures):

            result = future.result()

            if result:
                results.append(result)

    return sorted(
        results,
        key=lambda x: x["MAX"].tt
    )
