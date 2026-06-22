import uvicorn

if __name__ == "__main__":
    print("starting uvicorn...", flush=True)
    uvicorn.run(
        "api.main:app",
        host="127.0.0.1",
        port=8000,
        reload=True,
        reload_dirs=[
            "api",
            "core",
            "geometry",
            "infrastructure",
            "pipeline",
        ],
        log_level="debug",
    )
