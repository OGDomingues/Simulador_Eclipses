import json
from pathlib import Path
from functools import lru_cache

from api.services.real_eclipse_service import (
    get_real_eclipse,
)
from core import (
    classify_eclipse,
    new_moons,
)
from infrastructure.ephemeris import (
    get_context,
)
from pipeline.batch import (
    run_batch,
)

DATA_FILE = (
    Path(__file__)
    .parent.parent
    / "data"
    / "fake_eclipses.json"
)

with open(DATA_FILE, encoding="utf-8") as file:
    ECLIPSES = json.load(file)


def get_fake_eclipse(date: str):
    return ECLIPSES.get(
        date,
        ECLIPSES["2027-08-02"],
    )


def get_eclipse(date: str):
    """
    Troque para True quando quiser
    testar o motor real.
    """

    USE_REAL_ENGINE = True

    if USE_REAL_ENGINE:
        result = get_real_eclipse(date)

        if result is not None:
            return result

    return get_fake_eclipse(date)


@lru_cache(maxsize=1)
def get_available_eclipses():
    eph, ts = get_context()

    t_start = ts.utc(
        2020,
        1,
        1,
    )

    t_end = ts.utc(
        2040,
        12,
        31,
    )

    moons = new_moons(
        eph,
        t_start,
        t_end,
    )

    eclipses = run_batch(
        moons
    )

    result = []

    for eclipse in eclipses:
        c2 = eclipse.get("C2")
        c3 = eclipse.get("C3")

        if c2 is None or c3 is None:
            eclipse_type = "Parcial"
        else:
            eclipse_type = classify_eclipse(
                eph=eph,
                central_times=[
                    eclipse["MAX"]
                ],
                max_obscuration=1.0,
            )

        result.append(
            {
                "date": eclipse["MAX"]
                .utc_datetime()
                .date()
                .isoformat(),

                "type": eclipse_type,
            }
        )

    return result
