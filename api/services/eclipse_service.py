import json
from pathlib import Path

from api.services.real_eclipse_service import (
    get_real_eclipse,
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