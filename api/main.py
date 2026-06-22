from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.services.eclipse_service import (
    get_eclipse,
)

from api.services.circumstances_service import (
    get_circumstances,
    get_local_animation,
    get_local_maximum,
)
from api.services.obscuration_service import (
    get_obscuration_map,
    get_shadow_frame,
)
app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://localhost:5174",
        "http://localhost:5175",
        "http://localhost:5176",
        "http://localhost:5177",
        "http://localhost:5178",
        "http://localhost:5179",
        "http://127.0.0.1:5173",
        "http://127.0.0.1:5174",
        "http://127.0.0.1:5175",
        "http://127.0.0.1:5176",
        "http://127.0.0.1:5177",
        "http://127.0.0.1:5178",
        "http://127.0.0.1:5179",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/eclipse/{date}")
def eclipse(date: str):
    return get_eclipse(date)


@app.get("/api/circumstances")
def circumstances(
    date: str,
    lat: float,
    lon: float,
    time: str | None = None,
):
    result = get_circumstances(
        date,
        lat,
        lon,
        time,
    )

    if result is None:
        return {
            "error":
            "Eclipse não encontrado"
        }

    return result


@app.get("/api/local-maximum")
def local_maximum(
    date: str,
    lat: float,
    lon: float,
):
    result = get_local_maximum(
        date,
        lat,
        lon,
    )

    if result is None:
        return {
            "error":
            "Eclipse nÃ£o encontrado"
        }

    return result


@app.get("/api/local-animation")
def local_animation(
    date: str,
    lat: float,
    lon: float,
    step_seconds: int = 120,
):
    result = get_local_animation(
        date,
        lat,
        lon,
        step_seconds,
    )

    if result is None:
        return {
            "error":
            "Eclipse nÃ£o encontrado"
        }

    return result


@app.get(
    "/api/obscuration/{date}"
)
def obscuration(
    date: str,
):
    return get_obscuration_map(
        date
    )


@app.get("/api/shadow-frame")
def shadow_frame(
    time: str,
    lat_step: float = 2.0,
    lon_step: float = 2.0,
    min_obscuration: float = 0.001,
):
    result = get_shadow_frame(
        time,
        lat_step,
        lon_step,
        min_obscuration,
    )

    if result is None:
        return {
            "error":
            "Tempo invÃ¡lido"
        }

    return result

from api.services.geojson_service import (
    get_geojson,
)

@app.get(
    "/api/geojson/{date}"
)
def geojson(
    date: str
):
    return get_geojson(date)

@app.get(
    "/api/central-path/{date}"
)
def get_central_path(
    date: str
):
    from api.services.central_path_service import (
        get_central_path_data,
    )

    return get_central_path_data(
        date
    )

@app.get("/api/eclipses")
def list_eclipses():
    from api.services.eclipse_service import (
        get_available_eclipses,
    )

    return get_available_eclipses()
