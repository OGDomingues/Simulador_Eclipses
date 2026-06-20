from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.services.eclipse_service import (
    get_eclipse,
)

from api.services.circumstances_service import (
    get_circumstances,
)
from api.services.obscuration_service import (
    get_obscuration_map,
)
app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
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
):
    result = get_circumstances(
        date,
        lat,
        lon,
    )

    if result is None:
        return {
            "error":
            "Eclipse não encontrado"
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