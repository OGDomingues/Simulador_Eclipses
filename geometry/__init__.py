_EXPORTS = {
    "central_path": ("geometry.central_path", "central_path"),
    "eclipse_bounding_box": ("geometry.bounding_box", "eclipse_bounding_box"),
    "eclipse_obscuration_map": ("geometry.surface_map", "eclipse_obscuration_map"),
    "export_eclipse_geojson": ("geometry.export", "export_eclipse_geojson"),
    "export_eclipse_kml": ("geometry.export", "export_eclipse_kml"),
}

__all__ = list(_EXPORTS)


def __getattr__(name):
    if name not in _EXPORTS:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

    module_name, attribute_name = _EXPORTS[name]

    from importlib import import_module

    value = getattr(
        import_module(module_name),
        attribute_name,
    )
    globals()[name] = value
    return value
