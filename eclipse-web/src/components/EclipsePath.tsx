import * as Cesium from "cesium";

export function addPath(
  viewer: Cesium.Viewer,
  coords: number[][]
) {
  const flat = coords.flat();

  viewer.entities.add({
    polyline: {
      positions:
        Cesium.Cartesian3.fromDegreesArray(
          flat
        ),
      width: 4,
    },
  });
}