from skyfield.api import Loader, load, load_file

from .config import EPHEMERIS_PATH

_TS = None
_EPH = None


def get_context():

    global _TS, _EPH

    if _TS is None:
        _TS = load.timescale()

    if _EPH is None:
        EPHEMERIS_PATH.parent.mkdir(
            parents=True,
            exist_ok=True
        )

        if EPHEMERIS_PATH.exists():
            _EPH = load_file(
                str(EPHEMERIS_PATH)
            )
        else:
            print(
                "Efemeride nao encontrada. "
                f"Baixando {EPHEMERIS_PATH.name}..."
            )
            loader = Loader(
                str(EPHEMERIS_PATH.parent)
            )
            _EPH = loader(
                EPHEMERIS_PATH.name
            )

    return _EPH, _TS
