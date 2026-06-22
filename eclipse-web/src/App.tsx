import { useEffect, useRef, useState } from "react";
import * as Cesium from "cesium";

import "cesium/Build/Cesium/Widgets/widgets.css";

const API_BASE_URL =
  import.meta.env.VITE_API_BASE_URL ?? "http://127.0.0.1:8000";

type CentralPathPoint = {
  lat: number;
  lon: number;
  time: string;
};

type BestObservationPoint = CentralPathPoint & {
  index: number;
};

type EclipseData = {
  centralPath: CentralPathPoint[];

  northLimit: CentralPathPoint[];

  southLimit: CentralPathPoint[];

  bestObservation?: BestObservationPoint | null;
};

type GeoJsonLineFeature = {
  type: "Feature";
  properties?: {
    name?: string;
    level?: number;
  };
  geometry?: {
    type: "LineString";
    coordinates: number[][];
  };
};

type GeoJsonFeatureCollection = {
  type: "FeatureCollection";
  features: GeoJsonLineFeature[];
};

type EclipseSummary = {
  date: string;
  type: string;
};

type Circumstances = {
  obscuration: number;
  magnitude?: number;
  geometric_obscuration?: number;
  geometric_magnitude?: number;
  duration_sec?: number | null;
  totality_duration_sec?: number | null;
  c1: string | null;
  c2: string | null;
  max: string | null;
  c3: string | null;
  c4: string | null;
  sun_alt: number;
  sun_az: number;
  moon_alt?: number;
  moon_az?: number;
  sun_radius_deg?: number;
  moon_radius_deg?: number;
  separation_deg?: number;
  current_time?: string | null;
  sun_disc_below_horizon?: boolean;
  moon_disc_below_horizon?: boolean;
  bodies_below_horizon?: boolean;
  visible?: boolean;
};

type LocalAnimation = {
  date: string;
  lat: number;
  lon: number;
  step_seconds: number;
  max_frame_index: number;
  maximum: Circumstances;
  frames: Circumstances[];
};

type ShadowPoint = {
  lat: number;
  lon: number;
  obscuration: number;
};

type ShadowFrame = {
  time: string;
  count: number;
  points: ShadowPoint[];
};

type PolylineStyle = {
  width: number;
  material: Cesium.MaterialProperty;
  clampToGround?: boolean;
  smooth?: boolean;
  smoothSteps?: number; // number of interpolated points between each original pair
};

type SceneWithMsaa = Cesium.Scene & {
  msaaSamples?: number;
};

type ExtendedPolylineGraphics = Omit<
  Cesium.PolylineGraphics,
  "clampToGround" | "arcType"
> & {
  clampToGround?: boolean;
  arcType?: Cesium.ArcType;
};

type GeoJsonPositionsProperty = {
  getValue?: (
    time: Cesium.JulianDate
  ) => Cesium.Cartesian3[] | undefined;
};

function formatDate(
  value: string | null
) {
  if (
    !value ||
    value === "None" ||
    value === "null"
  ) {
    return "-";
  }

  const date = new Date(value);

  if (
    isNaN(date.getTime())
  ) {
    return "-";
  }

  return date.toLocaleString(
    "pt-BR",
    {
      day: "2-digit",
      month: "2-digit",
      year: "numeric",
      hour: "2-digit",
      minute: "2-digit",
      second: "2-digit",
      timeZone: "UTC",
    }
  );
}

function formatDateOnly(
  value: string
) {
  const [year, month, day] =
    value.split("-");

  if (!year || !month || !day) {
    return value;
  }

  return `${day}/${month}/${year}`;
}

function formatDurationSeconds(
  totalSeconds: number | null | undefined
) {
  if (totalSeconds == null || !Number.isFinite(totalSeconds) || totalSeconds <= 0) {
    return "-";
  }

  const s = Math.round(totalSeconds);
  const hours = Math.floor(s / 3600);
  const minutes = Math.floor((s % 3600) / 60);
  const seconds = s % 60;

  if (hours > 0) {
    return `${hours}h ${minutes}m ${seconds}s`;
  }
  if (minutes > 0) {
    return `${minutes}m ${seconds}s`;
  }
  return `${seconds}s`;
}

function shadowTextureDataUrl(
  frame: ShadowFrame,
  latStep: number,
  lonStep: number,
  anchor?: CentralPathPoint
) {
  const width = 2048;
  const height = 1024;
  const sourceStep =
    Math.max(
      0.15,
      Math.min(latStep, lonStep) / 3
    );
  const sourceWidth =
    Math.round(360 / sourceStep) + 1;
  const sourceHeight =
    Math.round(180 / sourceStep) + 1;
  const sourceCanvas =
    document.createElement("canvas");
  sourceCanvas.width = sourceWidth;
  sourceCanvas.height = sourceHeight;
  const sourceContext =
    sourceCanvas.getContext("2d");
  const canvas =
    document.createElement("canvas");
  canvas.width = width;
  canvas.height = height;

  const context =
    canvas.getContext("2d");

  if (!context || !sourceContext) {
    return null;
  }

  function shadowColor(
    obscuration: number
  ) {
    if (obscuration >= 0.99) {
      return [98, 66, 122, 210];
    }
    if (obscuration >= 0.9) {
      return [194, 75, 66, 185];
    }
    if (obscuration >= 0.4) {
      return [220, 146, 72, 150];
    }
    if (obscuration >= 0.001) {
      return [222, 204, 112, 95];
    }

    return [0, 0, 0, 0];
  }

  const imageData =
    sourceContext.createImageData(
      sourceWidth,
      sourceHeight
    );
  const sourceRadius =
    Math.max(
      1,
      Math.ceil(
        (Math.max(latStep, lonStep) / sourceStep) *
          0.45
      )
    );
  const highPoints =
    frame.points.filter(
      (point) =>
        point.obscuration >= 0.9
    );
  const anchorPoints =
    highPoints.length > 0
      ? highPoints
      : frame.points;
  const weightedCenter =
    anchorPoints.reduce(
      (acc, point) => {
        const weight =
          Math.max(
            0.001,
            point.obscuration
          );
        const radians =
          Cesium.Math.toRadians(point.lon);

        return {
          lat:
            acc.lat + point.lat * weight,
          sin:
            acc.sin +
            Math.sin(radians) * weight,
          cos:
            acc.cos +
            Math.cos(radians) * weight,
          weight:
            acc.weight + weight,
        };
      },
      {
        lat: 0,
        sin: 0,
        cos: 0,
        weight: 0,
      }
    );
  const centerPoint =
    weightedCenter.weight > 0
      ? {
          lat:
            weightedCenter.lat /
            weightedCenter.weight,
          lon:
            Cesium.Math.toDegrees(
              Math.atan2(
                weightedCenter.sin,
                weightedCenter.cos
              )
            ),
        }
      : null;
  const visualLatOffset =
    anchor && centerPoint
      ? anchor.lat - centerPoint.lat
      : 0;
  let visualLonOffset =
    anchor && centerPoint
      ? anchor.lon - centerPoint.lon
      : 0;

  while (visualLonOffset > 180) {
    visualLonOffset -= 360;
  }
  while (visualLonOffset < -180) {
    visualLonOffset += 360;
  }

  for (const point of frame.points) {
    let lon =
      point.lon + visualLonOffset;
    const lat =
      point.lat + visualLatOffset;

    while (lon > 180) {
      lon -= 360;
    }
    while (lon < -180) {
      lon += 360;
    }

    const x =
      Math.round(
        ((lon + 180) / 360) *
          (sourceWidth - 1)
      );
    const y =
      Math.round(
        ((90 - lat) / 180) *
          (sourceHeight - 1)
      );

    if (
      x < 0 ||
      x >= sourceWidth ||
      y < 0 ||
      y >= sourceHeight
    ) {
      continue;
    }

    const obscuration =
      Math.max(
        0,
        Math.min(1, point.obscuration)
      );
    const [r, g, b, a] =
      shadowColor(obscuration);

    for (let dy = -sourceRadius; dy <= sourceRadius; dy++) {
      for (let dx = -sourceRadius; dx <= sourceRadius; dx++) {
        if (
          dx * dx + dy * dy >
          sourceRadius * sourceRadius
        ) {
          continue;
        }

        const px = x + dx;
        const py = y + dy;

        if (
          px < 0 ||
          px >= sourceWidth ||
          py < 0 ||
          py >= sourceHeight
        ) {
          continue;
        }

        const offset =
          (py * sourceWidth + px) * 4;

        if (a >= imageData.data[offset + 3]) {
          imageData.data[offset] = r;
          imageData.data[offset + 1] = g;
          imageData.data[offset + 2] = b;
          imageData.data[offset + 3] = a;
        }
      }
    }
  }

  sourceContext.putImageData(
    imageData,
    0,
    0
  );
  context.clearRect(0, 0, width, height);
  context.imageSmoothingEnabled = true;
  context.imageSmoothingQuality = "high";
  context.filter = "blur(1.5px)";
  context.drawImage(
    sourceCanvas,
    0,
    0,
    width,
    height
  );
  context.filter = "none";

  return canvas.toDataURL("image/png");
}

function extractLimit(
  geojson: GeoJsonFeatureCollection,
  name: string
) {
  const feature =
    geojson.features.find(
      (item) =>
        item.properties?.name === name &&
        item.geometry?.type === "LineString"
    );

  return (
    feature?.geometry?.coordinates.map(
      ([lon, lat]) => ({
        lat,
        lon,
        time: "",
      })
    ) ?? []
  );
}

function EclipsePreview({
  circumstances,
}: {
  circumstances: Circumstances;
}) {
  const sunRadiusDeg = circumstances.sun_radius_deg ?? null;
  const moonRadiusDeg = circumstances.moon_radius_deg ?? null;
  const separationDeg = circumstances.separation_deg ?? null;

  const width = 220;
  const height = 160;
  const horizonY = 128;
  const wideSunR = 4;
  const zoomSunR = 29;

  const ratio =
    sunRadiusDeg && moonRadiusDeg && sunRadiusDeg > 0
      ? moonRadiusDeg / sunRadiusDeg
      : 1;
  const sunAlt = circumstances.sun_alt ?? 0;
  const moonAlt = circumstances.moon_alt ?? sunAlt;
  const sunAz = circumstances.sun_az ?? 0;
  const moonAz = circumstances.moon_az ?? sunAz;

  function clamp(value: number, min: number, max: number) {
    return Math.max(min, Math.min(max, value));
  }

  function azDeltaDegrees(a: number, b: number) {
    let delta = a - b;
    while (delta > 180) delta -= 360;
    while (delta < -180) delta += 360;
    return delta;
  }

  function smoothstep(edge0: number, edge1: number, value: number) {
    const t = clamp((value - edge0) / (edge1 - edge0), 0, 1);
    return t * t * (3 - 2 * t);
  }

  const gapDeg =
    separationDeg != null &&
    sunRadiusDeg != null &&
    moonRadiusDeg != null
      ? separationDeg - (sunRadiusDeg + moonRadiusDeg)
      : Number.POSITIVE_INFINITY;
  const contactScale =
    1 - smoothstep(-0.04, 2.4, gapDeg);

  const meanAlt =
    Cesium.Math.toRadians((sunAlt + moonAlt) / 2);
  const rawRelativeAz =
    azDeltaDegrees(moonAz, sunAz) *
    Math.cos(meanAlt);
  const rawRelativeAlt =
    moonAlt - sunAlt;
  const rawSeparationDeg = Math.hypot(rawRelativeAz, rawRelativeAlt);
  const visualSeparationDeg =
    separationDeg ?? rawSeparationDeg;
  const separationDirectionScale =
    rawSeparationDeg > 0.0001
      ? visualSeparationDeg / rawSeparationDeg
      : 1;
  const relativeAz =
    rawSeparationDeg > 0.0001
      ? rawRelativeAz * separationDirectionScale
      : visualSeparationDeg;
  const relativeAlt =
    rawSeparationDeg > 0.0001
      ? rawRelativeAlt * separationDirectionScale
      : 0;
  const safeSunRadiusDeg = sunRadiusDeg ?? 0.27;
  const safeMoonRadiusDeg = moonRadiusDeg ?? safeSunRadiusDeg * ratio;
  const horizonDisplayAlt = 0.8;
  const lowestBodyAlt = Math.min(sunAlt, moonAlt);
  const highestBodyAlt = Math.max(sunAlt, moonAlt);
  const showHorizon = lowestBodyAlt < horizonDisplayAlt;
  const horizonBlend = showHorizon
    ? 1 - smoothstep(horizonDisplayAlt - 2, horizonDisplayAlt, lowestBodyAlt)
    : 0;
  const horizonLineOpacity = showHorizon
    ? Math.max(0.78, horizonBlend)
    : 0;
  const targetSunR =
    wideSunR +
    (zoomSunR - wideSunR) *
      contactScale;
  const desiredPxPerDeg =
    targetSunR / safeSunRadiusDeg;
  const marginX = 16;
  const marginTop = 24;
  const marginBottom = showHorizon ? 8 : 22;
  const leftExtentDeg =
    Math.min(-safeSunRadiusDeg, relativeAz - safeMoonRadiusDeg);
  const rightExtentDeg =
    Math.max(safeSunRadiusDeg, relativeAz + safeMoonRadiusDeg);
  const topExtentDeg =
    Math.min(-safeSunRadiusDeg, -relativeAlt - safeMoonRadiusDeg);
  const bottomExtentDeg =
    Math.max(safeSunRadiusDeg, -relativeAlt + safeMoonRadiusDeg);
  const spanXDeg = Math.max(0.01, rightExtentDeg - leftExtentDeg);
  const spanYDeg = Math.max(0.01, bottomExtentDeg - topExtentDeg);
  const centeredFitPxPerDeg = Math.min(
    (width - marginX * 2) / spanXDeg,
    (height - marginTop - marginBottom) / spanYDeg
  );
  const pxPerDeg = Math.min(desiredPxPerDeg, centeredFitPxPerDeg);
  const minBodyRadiusPx = showHorizon ? 5 : 1.2;
  const sunR = Math.max(minBodyRadiusPx, safeSunRadiusDeg * pxPerDeg);
  const moonR = Math.max(
    minBodyRadiusPx,
    Math.min(38, safeMoonRadiusDeg * pxPerDeg)
  );
  const maxBodyRadiusPx = Math.max(sunR, moonR);
  const horizonCeilingAlt =
    Math.max(highestBodyAlt, horizonDisplayAlt);
  const horizonTopFitPxPerDeg =
    (horizonY - marginTop - maxBodyRadiusPx) /
    Math.max(0.01, horizonCeilingAlt);
  const horizonPositionPxPerDeg = showHorizon
    ? Math.max(
        0,
        horizonTopFitPxPerDeg
      )
    : pxPerDeg;
  const skyDx = relativeAz * pxPerDeg;
  const skyDy = -relativeAlt * pxPerDeg;

  function horizonBodyY(
    altitude: number
  ) {
    return horizonY - altitude * horizonPositionPxPerDeg;
  }

  function fitShift(
    minValue: number,
    maxValue: number,
    minLimit: number,
    maxLimit: number
  ) {
    if (!Number.isFinite(minValue) || !Number.isFinite(maxValue)) {
      return 0;
    }

    if (maxValue - minValue > maxLimit - minLimit) {
      return (minLimit + maxLimit - minValue - maxValue) / 2;
    }

    if (minValue < minLimit) {
      return minLimit - minValue;
    }

    if (maxValue > maxLimit) {
      return maxLimit - maxValue;
    }

    return 0;
  }

  let renderedSunCx = width / 2 - skyDx / 2;
  let renderedSunCy = showHorizon
    ? horizonBodyY(sunAlt)
    : height / 2 - 2 - skyDy / 2;
  let moonCx = renderedSunCx + skyDx;
  let moonCy = showHorizon
    ? horizonBodyY(moonAlt)
    : renderedSunCy + skyDy;

  const sunDiscFullyBelowHorizon =
    circumstances.sun_disc_below_horizon ??
    sunAlt <= -safeSunRadiusDeg;
  const moonDiscFullyBelowHorizon =
    circumstances.moon_disc_below_horizon ??
    moonAlt <= -safeMoonRadiusDeg;
  const astronomicalBothBodiesBelowHorizon =
    circumstances.bodies_below_horizon ??
    (
      sunDiscFullyBelowHorizon &&
      moonDiscFullyBelowHorizon
    );

  const minVisibleX = Math.min(
    renderedSunCx - sunR,
    moonCx - moonR
  );
  const maxVisibleX = Math.max(
    renderedSunCx + sunR,
    moonCx + moonR
  );
  const minVisibleY = Math.min(
    renderedSunCy - sunR,
    moonCy - moonR
  );
  const maxVisibleY = Math.max(
    renderedSunCy + sunR,
    moonCy + moonR
  );
  const shiftX = fitShift(
    minVisibleX,
    maxVisibleX,
    marginX,
    width - marginX
  );
  const shiftY = showHorizon
    ? 0
    : fitShift(
        minVisibleY,
        maxVisibleY,
        marginTop,
        height - marginBottom
      );

  renderedSunCx += shiftX;
  moonCx += shiftX;
  renderedSunCy += shiftY;
  moonCy += shiftY;
  const effectiveContactScale = contactScale;
  const bothBodiesBelowHorizon = showHorizon
    ? renderedSunCy - sunR >= height &&
      moonCy - moonR >= height
    : astronomicalBothBodiesBelowHorizon;
  const sunAboveHorizon =
    !sunDiscFullyBelowHorizon;
  const shouldRenderBodies =
    !bothBodiesBelowHorizon;
  const hasContact =
    gapDeg <= 0 ||
    (circumstances.geometric_obscuration ??
      circumstances.obscuration ??
      0) > 0;

  const isTotality =
    sunAboveHorizon &&
    (circumstances.totality_duration_sec ?? 0) > 0 &&
    (circumstances.geometric_obscuration ??
      circumstances.obscuration ??
      0) >= 0.999;

  return (
    <svg
      width={width}
      height={height}
      viewBox={`0 0 ${width} ${height}`}
      style={{
        borderRadius: 8,
        background: "#0b1020",
        border: "1px solid #1b2240",
      }}
      aria-label="VisualizaÃ§Ã£o do eclipse"
    >
      <defs>
        <radialGradient id="sunGrad" cx="50%" cy="50%" r="50%">
          <stop offset="0%" stopColor="#fff2a6" />
          <stop offset="60%" stopColor="#ffd34d" />
          <stop offset="100%" stopColor="#ffb300" />
        </radialGradient>
        <radialGradient id="moonGrad" cx="35%" cy="35%" r="65%">
          <stop offset="0%" stopColor="#3a3f4a" />
          <stop offset="100%" stopColor="#0d0f14" />
        </radialGradient>
        <radialGradient id="coronaGrad" cx="50%" cy="50%" r="50%">
          <stop offset="0%" stopColor="#fff9d6" stopOpacity="0.95" />
          <stop offset="55%" stopColor="#ffe08a" stopOpacity="0.55" />
          <stop offset="100%" stopColor="#ffb300" stopOpacity="0.0" />
        </radialGradient>
        <linearGradient id="skyGrad" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor="#18233f" />
          <stop offset="68%" stopColor="#23395c" />
          <stop offset="100%" stopColor="#d18d58" />
        </linearGradient>
      </defs>

      <rect x={0} y={0} width={width} height={height} fill="url(#skyGrad)" />
      {showHorizon && (
        <g opacity={horizonBlend}>
          <rect
            x={0}
            y={horizonY}
            width={width}
            height={height - horizonY}
            fill="#1f2c24"
          />
        </g>
      )}

      {isTotality && (
        <>
          <style>
            {`
              @keyframes coronaPulse {
                0% { transform: scale(0.98); opacity: 0.55; }
                50% { transform: scale(1.04); opacity: 0.85; }
                100% { transform: scale(0.98); opacity: 0.55; }
              }
              @keyframes coronaDrift {
                0% { filter: blur(0.6px); }
                50% { filter: blur(1.4px); }
                100% { filter: blur(0.6px); }
              }
            `}
          </style>
          <g
            style={{
              transformOrigin: `${renderedSunCx}px ${renderedSunCy}px`,
              animation: "coronaPulse 2.8s ease-in-out infinite, coronaDrift 3.6s ease-in-out infinite",
            }}
          >
            <circle cx={renderedSunCx} cy={renderedSunCy} r={sunR * 1.55} fill="url(#coronaGrad)" />
            <circle cx={renderedSunCx} cy={renderedSunCy} r={sunR * 1.25} fill="url(#coronaGrad)" opacity={0.9} />
          </g>
        </>
      )}

      {shouldRenderBodies && (
        <circle cx={renderedSunCx} cy={renderedSunCy} r={sunR} fill="url(#sunGrad)" />
      )}
      {shouldRenderBodies && (
        <circle cx={moonCx} cy={moonCy} r={moonR} fill="url(#moonGrad)" opacity={0.95} />
      )}
      <text x={8} y={18} fill="#d6d9e6" fontSize={12} fontFamily="sans-serif">
        {isTotality
          ? "Totalidade"
          : bothBodiesBelowHorizon
            ? "Sol e Lua abaixo do horizonte"
            : hasContact
              ? "Eclipse local"
              : "Sol e Lua visiveis"}
      </text>
      {showHorizon && (
        <text x={8} y={horizonY - 6} fill="#f3d49a" fontSize={10} fontFamily="sans-serif" opacity={horizonBlend}>
          Horizonte
        </text>
      )}
      <text x={width - 8} y={height - 8} fill="#cbd3e8" fontSize={10} fontFamily="sans-serif" textAnchor="end">
        {effectiveContactScale > 0.35 ? "zoom contato" : "visao ampla"}
      </text>
      {showHorizon && (
        <line
          x1={0}
          y1={horizonY}
          x2={width}
          y2={horizonY}
          stroke="#ffd38a"
          strokeOpacity={horizonLineOpacity}
          strokeWidth={1.5}
          vectorEffect="non-scaling-stroke"
          pointerEvents="none"
        />
      )}
    </svg>
  );
}

export default function App() {
  const viewerRef = useRef<HTMLDivElement>(null);

  const viewerInstance =
    useRef<Cesium.Viewer | null>(null);

  const clickMarker =
    useRef<Cesium.Entity | null>(null);

  const eclipseMarker =
    useRef<Cesium.Entity | null>(null);

  const bestObservationMarker =
    useRef<Cesium.Entity | null>(null);

  const shadowEntities =
    useRef<Cesium.Entity[]>([]);

  const [selectedDate, setSelectedDate] =
    useState("2027-08-02");

  const [sidebarOpen, setSidebarOpen] =
    useState(true);
  const [sidebarView, setSidebarView] =
    useState<"general" | "local">("general");
  const [eclipseData, setEclipseData] =
    useState<EclipseData | null>(null);

  const [pathIndex, setPathIndex] =
    useState(0);

  const [playing, setPlaying] =
    useState(false);

  const [circumstances, setCircumstances] =
    useState<Circumstances | null>(null);

  const [clickedLat, setClickedLat] =
    useState<number | null>(null);

  const [clickedLon, setClickedLon] =
    useState<number | null>(null);

  const [
    localAnimation,
    setLocalAnimation,
  ] = useState<LocalAnimation | null>(null);

  const [
    localFrameIndex,
    setLocalFrameIndex,
  ] = useState(0);

  const [
    localPlaying,
    setLocalPlaying,
  ] = useState(false);

  const displayedCircumstances =
    localAnimation?.frames[
      localFrameIndex
    ] ?? circumstances;
  const displayedHasGeometricContact =
    displayedCircumstances?.separation_deg != null &&
    displayedCircumstances.sun_radius_deg != null &&
    displayedCircumstances.moon_radius_deg != null
      ? displayedCircumstances.separation_deg <=
        displayedCircumstances.sun_radius_deg +
          displayedCircumstances.moon_radius_deg
      : (displayedCircumstances?.obscuration ?? 0) > 0;

const [
  eclipses,
  setEclipses
] = useState<EclipseSummary[]>([]);
  const selectedEclipseSummary =
    eclipses.find(
      (eclipse) =>
        eclipse.date === selectedDate
    ) ?? null;

  async function loadLocalVisualization(
    latitude: number,
    longitude: number
  ) {
    setLocalPlaying(false);
    setLocalAnimation(null);
    setLocalFrameIndex(0);

    const maximumParams =
      new URLSearchParams({
        date: selectedDate,
        lat: String(latitude),
        lon: String(longitude),
      });

    const maximumResponse =
      await fetch(
        `${API_BASE_URL}/api/local-maximum?${maximumParams.toString()}`
      );

    const maximum =
      (await maximumResponse.json()) as Circumstances;

    if (typeof maximum.obscuration !== "number") {
      setCircumstances(null);
      return;
    }

    setCircumstances(maximum);

    const animationParams =
      new URLSearchParams({
        date: selectedDate,
        lat: String(latitude),
        lon: String(longitude),
        step_seconds: "60",
      });

    const animationResponse =
      await fetch(
        `${API_BASE_URL}/api/local-animation?${animationParams.toString()}`
      );

    const animation =
      (await animationResponse.json()) as LocalAnimation;

    if (!Array.isArray(animation.frames)) {
      setLocalAnimation(null);
      setLocalFrameIndex(0);
      return;
    }

    setLocalAnimation(animation);
    setLocalFrameIndex(
      animation.max_frame_index ?? 0
    );
  }

  useEffect(() => {
  async function loadEclipses() {
    const response =
      await fetch(
        `${API_BASE_URL}/api/eclipses`
      );

    const data =
      (await response.json()) as EclipseSummary[];

    setEclipses(data);

    if (data.length) {
      setSelectedDate(
        data[0].date
      );
    }
  }

  void loadEclipses();
}, []);
  useEffect(() => {
    if (!viewerRef.current) return;

    Cesium.Ion.defaultAccessToken =
      import.meta.env.VITE_CESIUM_TOKEN;

    const viewer = new Cesium.Viewer(
      viewerRef.current,
      {
        timeline: false,
        animation: false,
        baseLayerPicker: true,
      }
    );

    viewerInstance.current = viewer;
    viewer.clock.shouldAnimate = false;
    viewer.scene.globe.enableLighting = true;
    viewer.scene.globe.dynamicAtmosphereLighting = true;
    viewer.scene.globe.dynamicAtmosphereLightingFromSun = true;
    viewer.scene.light = new Cesium.SunLight();
    if (viewer.scene.sun) {
      viewer.scene.sun.show = true;
    }
    if (viewer.scene.moon) {
      viewer.scene.moon.show = true;
    }

    // Improve polyline visual quality (reduce jaggies) on high-DPI displays.
    // FXAA is a post-process anti-aliasing pass; MSAA (when available) further smooths edges.
    try {
      viewer.scene.postProcessStages.fxaa.enabled = true;
    } catch {
      // ignore (older Cesium builds / environments)
    }
    // Cesium recommends setting resolutionScale for crisp rendering on HiDPI.
    // Clamp to avoid excessive GPU cost on very high DPR screens.
    viewer.resolutionScale = Math.min(
      2,
      window.devicePixelRatio || 1
    );
    const sceneWithMsaa =
      viewer.scene as SceneWithMsaa;
    if (typeof sceneWithMsaa.msaaSamples === "number") {
      sceneWithMsaa.msaaSamples = 4;
    }

    const handler =
      new Cesium.ScreenSpaceEventHandler(
        viewer.scene.canvas
      );

    handler.setInputAction(
      async (
        click: Cesium.ScreenSpaceEventHandler.PositionedEvent
      ) => {
        const cartesian =
          viewer.camera.pickEllipsoid(
            click.position,
            viewer.scene.globe.ellipsoid
          );

        if (!cartesian) return;

        const cartographic =
          Cesium.Cartographic.fromCartesian(
            cartesian
          );

        const latitude =
          Cesium.Math.toDegrees(
            cartographic.latitude
          );

        const longitude =
          Cesium.Math.toDegrees(
            cartographic.longitude
          );

        setClickedLat(latitude);
        setClickedLon(longitude);
        setSidebarView("local");

        if (clickMarker.current) {
          viewer.entities.remove(
            clickMarker.current
          );
        }

        clickMarker.current =
          viewer.entities.add({
            position:
              Cesium.Cartesian3.fromDegrees(
                longitude,
                latitude
              ),
            point: {
              pixelSize: 10,
              color: Cesium.Color.CYAN,
            },
          });

        try {
          await loadLocalVisualization(
            latitude,
            longitude
          );
        } catch (error) {
          console.error(error);
        }
      },
      Cesium.ScreenSpaceEventType.LEFT_CLICK
    );

    return () => {
      handler.destroy();

      if (!viewer.isDestroyed()) {
        viewer.destroy();
      }

      viewerInstance.current = null;
    };
  }, [selectedDate]);

  useEffect(() => {
  async function loadEclipse() {
    const viewer0 = viewerInstance.current;
    if (!viewer0) {
      return;
    }
    const viewer = viewer0;

    try {
        const response =
            await fetch(
                `${API_BASE_URL}/api/eclipse/${selectedDate}`
            );

        const eclipse =
            (await response.json()) as EclipseData;

        viewer.entities.removeAll();
        viewer.dataSources.removeAll();
        bestObservationMarker.current = null;
        eclipseMarker.current = null;
        shadowEntities.current = [];
        setCircumstances(null);
        setLocalAnimation(null);
        setLocalFrameIndex(0);
        setLocalPlaying(false);

        const geojsonResponse =
            await fetch(
                `${API_BASE_URL}/api/geojson/${selectedDate}`
            );

        const geojson =
            (await geojsonResponse.json()) as GeoJsonFeatureCollection;

        const eclipseWithLimits: EclipseData = {
          ...eclipse,
          northLimit: extractLimit(
            geojson,
            "north_limit"
          ),
          southLimit: extractLimit(
            geojson,
            "south_limit"
          ),
        };

        setEclipseData(eclipseWithLimits);
        const bestIdx =
          eclipse.bestObservation?.index ?? 0;
        setPathIndex(bestIdx);

        const dataSource =
            await Cesium.GeoJsonDataSource.load(
                geojson
            );

        viewer.dataSources.add(
            dataSource
        );

        console.log(
            "GeoJSON entities:",
            dataSource.entities.values.length
        );

        const now = Cesium.JulianDate.now();

        function normalizeLon(lonDeg: number) {
          // Normalize to [-180, 180)
          let x = ((lonDeg + 180) % 360 + 360) % 360 - 180;
          // Avoid -180 which can cause visual discontinuities when paired with +180
          if (x === -180) x = 180;
          return x;
        }

        function splitDegreesPath(
          degPairs: Array<[number, number]>
        ) {
          // Split path when we detect a dateline wrap or an obviously bogus jump.
          // This prevents the single long segment that "cuts across" continents/oceans.
          const segments: Array<Array<[number, number]>> = [];
          let cur: Array<[number, number]> = [];

          for (let i = 0; i < degPairs.length; i++) {
            const [lon0, lat0] = degPairs[i];
            const lon = normalizeLon(lon0);
            const lat = lat0;

            if (cur.length === 0) {
              cur.push([lon, lat]);
              continue;
            }

            const [prevLon, prevLat] = cur[cur.length - 1];
            const dLon = Math.abs(lon - prevLon);
            const dLat = Math.abs(lat - prevLat);

            // Heuristic: a jump > 180deg in longitude indicates wrap.
            // Also split on huge lat jumps which are never part of these contours.
            if (dLon > 180 || dLat > 30) {
              if (cur.length >= 2) segments.push(cur);
              cur = [[lon, lat]];
              continue;
            }

            // Additional heuristic using surface distance.
            // If two consecutive points are thousands of km apart, treat as discontinuity.
            const a = Cesium.Cartesian3.fromDegrees(prevLon, prevLat);
            const b = Cesium.Cartesian3.fromDegrees(lon, lat);
            const distM = Cesium.Cartesian3.distance(a, b);
            if (distM > 2_500_000) {
              if (cur.length >= 2) segments.push(cur);
              cur = [[lon, lat]];
              continue;
            }

            cur.push([lon, lat]);
          }

          if (cur.length >= 2) segments.push(cur);
          return segments;
        }

        function chaikinSmooth(
          seg: Array<[number, number]>,
          iterations: number
        ) {
          // Chaikin corner cutting: rounds "stair-step" contours without overshoot.
          // This is purely visual; it doesn't change any eclipse calculations.
          if (seg.length < 3 || iterations <= 0) return seg;

          let pts = seg;
          for (let it = 0; it < iterations; it++) {
            const out: Array<[number, number]> = [];
            out.push(pts[0]);
            for (let i = 0; i < pts.length - 1; i++) {
              const [x0, y0] = pts[i];
              const [x1, y1] = pts[i + 1];
              const q: [number, number] = [
                0.75 * x0 + 0.25 * x1,
                0.75 * y0 + 0.25 * y1,
              ];
              const r: [number, number] = [
                0.25 * x0 + 0.75 * x1,
                0.25 * y0 + 0.75 * y1,
              ];
              out.push(q, r);
            }
            out.push(pts[pts.length - 1]);
            pts = out;
          }
          return pts;
        }

        function rebuildPolylineEntity(
          entity: Cesium.Entity,
          style: PolylineStyle
        ) {
          if (!entity.polyline) return;
          const positionsProp =
            entity.polyline.positions as GeoJsonPositionsProperty | undefined;
          const positions: Cesium.Cartesian3[] | undefined =
            positionsProp?.getValue?.(now);
          if (!positions || positions.length < 2) return;

          const degPairs: Array<[number, number]> = positions.map((p) => {
            const c = Cesium.Cartographic.fromCartesian(p);
            const lat = Cesium.Math.toDegrees(c.latitude);
            const lon = Cesium.Math.toDegrees(c.longitude);
            return [lon, lat];
          });

          let segments = splitDegreesPath(degPairs);
          if (style.smooth) {
            // For contour-like lines, Chaikin smoothing gives a nicer look and avoids the
            // "spike / cross-connection" artifacts that can happen with spline overshoot.
            const iterations = style.smoothSteps ?? 2;
            segments = segments.map((s) => chaikinSmooth(s, iterations));
          }
          if (segments.length <= 1 && !style.smooth) {
            // Still apply style in-place.
            const polyline =
              entity.polyline as ExtendedPolylineGraphics;
            polyline.width = new Cesium.ConstantProperty(style.width);
            polyline.clampToGround = style.clampToGround ?? true;
            polyline.material = style.material;
            polyline.arcType = Cesium.ArcType.GEODESIC;
            return;
          }

          // Remove original GeoJSON entity and re-add the cleaned/smoothed segments.
          const name = entity.name;
          const props = entity.properties;
          dataSource.entities.remove(entity);

          for (const seg of segments) {
            dataSource.entities.add({
              name,
              properties: props,
              polyline: {
                positions: Cesium.Cartesian3.fromDegreesArray(
                  seg.flat() as number[]
                ),
                width: style.width,
                clampToGround: style.clampToGround ?? true,
                material: style.material,
                arcType: Cesium.ArcType.GEODESIC,
              },
            });
          }
        }

        function materialForColor(color: Cesium.Color) {
          // Cesium polylines are often jagged, especially when thick.
          // A subtle glow makes edges look smoother without changing meaning.
          return new Cesium.PolylineGlowMaterialProperty({
            color,
            glowPower: 0.18,
          });
        }

        // We rebuild/split polylines to avoid anti-meridian / discontinuity artifacts.
        // Also apply a glow material to reduce visible serrilhado on thick lines.
        const entitiesSnapshot = [...dataSource.entities.values];
        for (const entity of entitiesSnapshot) {
          const props = entity.properties;
          const level = props?.level?.getValue?.();
          const name = String(entity.name ?? "");

          if (!entity.polyline) continue;

          if (name === "north_limit" || name === "south_limit") {
            rebuildPolylineEntity(entity, {
              width: 7,
              material: materialForColor(Cesium.Color.YELLOW),
              clampToGround: true,
              smooth: true,
              smoothSteps: 1,
            });
            continue;
          }

          if (level >= 0.9) {
            rebuildPolylineEntity(entity, {
              width: 6,
              material: materialForColor(Cesium.Color.RED),
              clampToGround: true,
              smooth: true,
              smoothSteps: 2,
            });
          } else if (level >= 0.75) {
            rebuildPolylineEntity(entity, {
              width: 5,
              material: materialForColor(Cesium.Color.ORANGE),
              clampToGround: true,
              smooth: true,
              smoothSteps: 2,
            });
          } else if (level >= 0.5) {
            rebuildPolylineEntity(entity, {
              width: 4,
              material: materialForColor(Cesium.Color.YELLOW),
              clampToGround: true,
              smooth: true,
              smoothSteps: 2,
            });
          } else if (level >= 0.1) {
            rebuildPolylineEntity(entity, {
              width: 2,
              material: new Cesium.ColorMaterialProperty(
                Cesium.Color.fromCssColorString("#d8d8d8").withAlpha(0.9)
              ),
              clampToGround: true,
            });
          } else {
            rebuildPolylineEntity(entity, {
              // 0.1% visibility boundary
              width: 2,
              material: new Cesium.ColorMaterialProperty(
                Cesium.Color.fromCssColorString("#cfcfcf").withAlpha(0.7)
              ),
              clampToGround: true,
            });
          }
        }


function addLine(
  coords: number[][],
  color: Cesium.Color,
  width: number
) {
  viewer.entities.add({
    polyline: {
      positions:
        Cesium.Cartesian3.fromDegreesArray(
          coords.flat() as number[]
        ),
      width,
      material: materialForColor(color),
      clampToGround: true,
      arcType: Cesium.ArcType.GEODESIC,
    },
  });
}

      addLine(
        eclipse.centralPath.map(
          (p: CentralPathPoint) => [
            p.lon,
            p.lat,
          ]
        ),
        Cesium.Color.RED,
        6
      );

      const best =
        eclipse.bestObservation;

      if (
        best &&
        Number.isFinite(best.lat) &&
        Number.isFinite(best.lon)
      ) {
        // Also populate the sidebar automatically with circumstances for the best observation point.
        setClickedLat(best.lat);
        setClickedLon(best.lon);
        try {
          await loadLocalVisualization(
            best.lat,
            best.lon
          );
        } catch (error) {
          console.error(error);
        }

        const pinBuilder =
          new Cesium.PinBuilder();

        bestObservationMarker.current =
          viewer.entities.add({
            name:
              "Melhor local de observação",
            position:
              Cesium.Cartesian3.fromDegrees(
                best.lon,
                best.lat
              ),
            billboard: {
              image: pinBuilder
                .fromText(
                  "★",
                  Cesium.Color.GOLD,
                  48
                )
                .toDataURL(),
              verticalOrigin:
                Cesium.VerticalOrigin.BOTTOM,
              heightReference:
                Cesium.HeightReference.CLAMP_TO_GROUND,
            },
            label: {
              text:
                "Melhor observação",
              font:
                "14px sans-serif",
              fillColor:
                Cesium.Color.WHITE,
              outlineColor:
                Cesium.Color.BLACK,
              outlineWidth: 3,
              style:
                Cesium.LabelStyle.FILL_AND_OUTLINE,
              pixelOffset:
                new Cesium.Cartesian2(
                  0,
                  -54
                ),
              verticalOrigin:
                Cesium.VerticalOrigin.BOTTOM,
              heightReference:
                Cesium.HeightReference.CLAMP_TO_GROUND,
              disableDepthTestDistance:
                Number.POSITIVE_INFINITY,
            },
          });

        viewer.camera.flyTo({
          destination:
            Cesium.Cartesian3.fromDegrees(
              best.lon,
              best.lat,
              1_800_000
            ),
          orientation: {
            heading: 0,
            pitch:
              -Cesium.Math.PI_OVER_TWO,
            roll: 0,
          },
          duration: 0.8,
        });
      } else {
        await viewer.zoomTo(
          dataSource
        );
      }
    } catch (error) {
      console.error(
        "Erro ao carregar eclipse:",
        error
      );
    }
  }
    void loadEclipse();
}, [selectedDate]);

  useEffect(() => {
    const viewer =
      viewerInstance.current;

    if (
      !viewer ||
      !eclipseData ||
      eclipseData.centralPath.length === 0
    ) {
      return;
    }

    const point =
      eclipseData.centralPath[pathIndex];
    const frameTime =
      Cesium.JulianDate.fromIso8601(
        point.time
      );

    viewer.clock.currentTime =
      frameTime;
    viewer.clock.multiplier = 1;
    viewer.clock.shouldAnimate = false;

    if (eclipseMarker.current) {
      viewer.entities.remove(
        eclipseMarker.current
      );
    }

    eclipseMarker.current =
      viewer.entities.add({
        position:
          Cesium.Cartesian3.fromDegrees(
            point.lon,
            point.lat
          ),

        point: {
          pixelSize: 12,
          color: Cesium.Color.YELLOW,
          outlineColor:
            Cesium.Color.BLACK,
          outlineWidth: 2,
        },
      });
    viewer.scene.requestRender();
  }, [pathIndex, eclipseData]);

  useEffect(() => {
    const viewer =
      viewerInstance.current;

    if (
      !viewer ||
      !eclipseData ||
      eclipseData.centralPath.length === 0
    ) {
      return;
    }

    const point =
      eclipseData.centralPath[pathIndex];
    const controller =
      new AbortController();
    const timer =
      window.setTimeout(
        async () => {
          try {
            const params =
              new URLSearchParams({
                time: point.time,
                lat_step: "0.75",
                lon_step: "0.75",
                min_obscuration: "0.001",
              });

            const response =
              await fetch(
                `${API_BASE_URL}/api/shadow-frame?${params.toString()}`,
                {
                  signal: controller.signal,
                }
              );

            const frame =
              (await response.json()) as ShadowFrame;

            if (!Array.isArray(frame.points)) {
              return;
            }

            for (const entity of shadowEntities.current) {
              viewer.entities.remove(entity);
            }
            shadowEntities.current = [];

            const texture =
              shadowTextureDataUrl(
                frame,
                0.75,
                0.75,
                point
              );

            if (texture) {
              const entity =
                viewer.entities.add({
                  name:
                    "Sombra calculada da Lua",
                  rectangle: {
                    coordinates:
                      Cesium.Rectangle.fromDegrees(
                        -180,
                        -90,
                        180,
                        90
                      ),
                    material:
                      new Cesium.ImageMaterialProperty({
                        image: texture,
                        transparent: true,
                      }),
                    height: 12_000,
                  },
                });

              shadowEntities.current.push(
                entity
              );
            }
            viewer.scene.requestRender();
          } catch (error) {
            if (
              error instanceof DOMException &&
              error.name === "AbortError"
            ) {
              return;
            }

            console.error(error);
          }
        },
        playing ? 220 : 120
      );

    return () => {
      window.clearTimeout(timer);
      controller.abort();
    };
  }, [
    pathIndex,
    eclipseData,
    playing,
  ]);

  useEffect(() => {
  if (
    !playing ||
    !eclipseData
  ) {
    return;
  }

  const timer =
    setInterval(() => {
      setPathIndex(
        (current) => {
          const next =
            current + 1;

          if (
            next >=
            eclipseData
              .centralPath.length
          ) {
            setPlaying(
              false
            );

            return current;
          }

          return next;
        }
      );
    }, 100);

  return () =>
    clearInterval(timer);
}, [
  playing,
  eclipseData,
]);

  useEffect(() => {
    if (
      !localPlaying ||
      !localAnimation ||
      localAnimation.frames.length === 0
    ) {
      return;
    }

    const timer =
      setInterval(() => {
        setLocalFrameIndex(
          (current) => {
            const next =
              current + 1;

            if (
              next >=
              localAnimation.frames.length
            ) {
              setLocalPlaying(false);
              return current;
            }

            return next;
          }
        );
      }, 140);

    return () =>
      clearInterval(timer);
  }, [
    localPlaying,
    localAnimation,
  ]);


  return (
    <div
      style={{
        display: "flex",
        width: "100vw",
        height: "100vh",
      }}
    >
      <div
        style={{
          flex: 1,
          position: "relative",
        }}
      >
        <div
          style={{
            position: "absolute",
            top: 10,
            left: 10,
            zIndex: 1000,
            background: "white",
            padding: "10px",
            borderRadius: "6px",
            boxShadow:
              "0 2px 6px rgba(0,0,0,0.2)",
          }}
        >
          <select
  value={selectedDate}
  onChange={(e) =>
    setSelectedDate(
      e.target.value
    )
  }
>
  {eclipses.map(
    (eclipse) => (
      <option
        key={eclipse.date}
        value={eclipse.date}
      >
        {formatDateOnly(
          eclipse.date
        )}
        {" - "}
        Eclipse {eclipse.type}
      </option>
    )
  )}
</select>
        </div>

        <div
          ref={viewerRef}
          style={{
            width: "100%",
            height: "100%",
          }}
        />
      </div>

      <div
        style={{
          width: sidebarOpen
            ? "360px"
            : "42px",

          transition:
            "width 300ms ease",

          background: "#ffffff",

          borderLeft:
            "1px solid #ddd",

          overflow: "hidden",

          position: "relative",

          boxShadow:
            "-2px 0 10px rgba(0,0,0,0.08)",
        }}
      >
        <button
          onClick={() =>
            setSidebarOpen(
              !sidebarOpen
            )
          }
          style={{
            position: "absolute",
            top: 10,
            left: 6,

            width: 30,
            height: 30,

            border: "none",
            borderRadius: "6px",

            background: "#f0f0f0",

            cursor: "pointer",

            zIndex: 1000,
          }}
        >
          {sidebarOpen ? "❯" : "❮"}
        </button>

        <div
          style={{
            opacity:
              sidebarOpen ? 1 : 0,

            transform:
              sidebarOpen
                ? "translateX(0)"
                : "translateX(20px)",

            transition:
              "all 250ms ease",

            padding: "16px",

            pointerEvents:
              sidebarOpen
                ? "auto"
                : "none",
          }}
        >
          <div
            style={{
              display: "grid",
              gridTemplateColumns: "1fr 1fr",
              gap: "6px",
              marginBottom: "14px",
            }}
          >
            <button
              onClick={() =>
                setSidebarView("general")
              }
              style={{
                padding: "7px 8px",
                border:
                  sidebarView === "general"
                    ? "1px solid #3d7778"
                    : "1px solid #d0d0d0",
                borderRadius: "6px",
                background:
                  sidebarView === "general"
                    ? "#e8f3f3"
                    : "#f8f8f8",
                cursor: "pointer",
              }}
            >
              Geral
            </button>

            <button
              onClick={() =>
                setSidebarView("local")
              }
              style={{
                padding: "7px 8px",
                border:
                  sidebarView === "local"
                    ? "1px solid #3d7778"
                    : "1px solid #d0d0d0",
                borderRadius: "6px",
                background:
                  sidebarView === "local"
                    ? "#e8f3f3"
                    : "#f8f8f8",
                cursor: "pointer",
              }}
            >
              Local
            </button>
          </div>

          {sidebarView === "general" && (
            <>
              <h2>
                Dados Gerais
              </h2>

              <div
                style={{
                  display: "flex",
                  justifyContent:
                    "space-between",
                  gap: "10px",
                }}
              >
                <strong>Data:</strong>
                <span>
                  {formatDateOnly(
                    selectedDate
                  )}
                </span>
              </div>

              <div
                style={{
                  display: "flex",
                  justifyContent:
                    "space-between",
                  gap: "10px",
                }}
              >
                <strong>Tipo:</strong>
                <span>
                  {selectedEclipseSummary?.type ??
                    "-"}
                </span>
              </div>

              {eclipseData?.bestObservation && (
                <div
                  style={{
                    display: "flex",
                    justifyContent:
                      "space-between",
                    gap: "10px",
                  }}
                >
                  <strong>
                    Melhor local:
                  </strong>
                  <span>
                    {eclipseData.bestObservation.lat.toFixed(
                      2
                    )}
                    ,{" "}
                    {eclipseData.bestObservation.lon.toFixed(
                      2
                    )}
                  </span>
                </div>
              )}

              <hr />

{eclipseData && (
  <>
    <h3>
      Linha do Tempo
    </h3>
    <div
  style={{
    display: "flex",
    gap: "8px",
    marginBottom: "10px",
  }}
>
  <button
    onClick={() =>
      setPlaying(
        !playing
      )
    }
  >
    {playing
      ? "⏸ Pause"
      : "▶ Play"}
  </button>

  <button
    onClick={() => {
      setPlaying(
        false
      );

      setPathIndex(0);
    }}
  >
    ⏮ Reset
  </button>
</div>
    <input
      type="range"
      min={0}
      max={
        eclipseData.centralPath.length - 1
      }
      value={pathIndex}
      onChange={(e) =>
        setPathIndex(
          Number(e.target.value)
        )
      }
      style={{
        width: "100%",
      }}
    />

    <div
  style={{
    marginBottom: "16px",
    fontFamily:
      "monospace",
  }}
>
  {formatDate(
    eclipseData.centralPath[
      pathIndex
    ]?.time ?? null
  )}
</div>

    <hr />
  </>
)}
            </>
          )}

          {sidebarView === "local" && (
            <>
          <h2>
            Circunstâncias Locais
          </h2>

          <div>
            <strong>Latitude:</strong>{" "}
            {clickedLat?.toFixed(4) ??
              "-"}
          </div>

          <div>
            <strong>Longitude:</strong>{" "}
            {clickedLon?.toFixed(4) ??
              "-"}
          </div>

          {localAnimation && (
  <>
    <hr />

    <h3>
      Animacao local
    </h3>

    <div
      style={{
        display: "flex",
        gap: "8px",
        marginBottom: "10px",
      }}
    >
      <button
        onClick={() =>
          setLocalPlaying(
            !localPlaying
          )
        }
      >
        {localPlaying
          ? "Pause"
          : "Play"}
      </button>

      <button
        onClick={() => {
          setLocalPlaying(false);
          setLocalFrameIndex(
            localAnimation.max_frame_index ?? 0
          );
        }}
      >
        Maximo
      </button>
    </div>

    <input
      type="range"
      min={0}
      max={
        localAnimation.frames.length - 1
      }
      value={localFrameIndex}
      onChange={(e) => {
        setLocalPlaying(false);
        setLocalFrameIndex(
          Number(e.target.value)
        );
      }}
      style={{
        width: "100%",
      }}
    />

    <div
      style={{
        marginBottom: "12px",
        fontFamily:
          "monospace",
      }}
    >
      {formatDate(
        displayedCircumstances?.current_time ?? null
      )}
    </div>
  </>
)}

          {displayedCircumstances && (
  <>
    <hr />

    <div
      style={{
        display: "flex",
        justifyContent:
          "space-between",
        gap: "10px",
      }}
    >
      <strong>
        Obscuração:
      </strong>

      <span>
        {(
          displayedCircumstances.obscuration *
          100
        ).toFixed(2)}
        %
      </span>
    </div>

    <div
      style={{
        display: "flex",
        justifyContent: "space-between",
        gap: "10px",
      }}
    >
      <strong>
        Magnitude:
      </strong>

      <span>
        {(displayedCircumstances.magnitude ?? 0).toFixed(4)}
      </span>
    </div>

    <div
      style={{
        display: "flex",
        justifyContent: "space-between",
        gap: "10px",
      }}
    >
      <strong>
        Duração:
      </strong>

      <span>
        {formatDurationSeconds(
          displayedCircumstances.duration_sec
        )}
      </span>
    </div>

    <div
      style={{
        display: "flex",
        justifyContent: "space-between",
        gap: "10px",
      }}
    >
      <strong>
        Duração Totalidade:
      </strong>

      <span>
        {formatDurationSeconds(
          displayedCircumstances.totality_duration_sec
        )}
      </span>
    </div>

    <div
      style={{
        marginTop: "12px",
        marginBottom: "10px",
        display: "flex",
        justifyContent: "center",
      }}
    >
      <EclipsePreview
        circumstances={displayedCircumstances}
      />
    </div>

    {!displayedHasGeometricContact && (
      <div
        style={{
          marginBottom: "12px",
          color: "#666",
          fontStyle: "italic",
        }}
      >
        Sol e Lua sem contato neste instante.
      </div>
    )}

        <div
          style={{
            display: "flex",
            justifyContent:
              "space-between",
            gap: "10px",
          }}
        >
          <strong>C1:</strong>

          <span>
            {formatDate(
              displayedCircumstances.c1
            )}
          </span>
        </div>

        {displayedCircumstances.c2 &&
          displayedCircumstances.c2 !==
            "None" && (
            <div
              style={{
                display: "flex",
                justifyContent:
                  "space-between",
                gap: "10px",
              }}
            >
              <strong>C2:</strong>

              <span>
                {formatDate(
                  displayedCircumstances.c2
                )}
              </span>
            </div>
        )}

        <div
          style={{
            display: "flex",
            justifyContent:
              "space-between",
            gap: "10px",
          }}
        >
          <strong>
            Máximo:
          </strong>

          <span>
            {formatDate(
              displayedCircumstances.max
            )}
          </span>
        </div>

        {displayedCircumstances.c3 &&
          displayedCircumstances.c3 !==
            "None" && (
            <div
              style={{
                display: "flex",
                justifyContent:
                  "space-between",
                gap: "10px",
              }}
            >
              <strong>C3:</strong>

              <span>
                {formatDate(
                  displayedCircumstances.c3
                )}
              </span>
            </div>
        )}

        <div
          style={{
            display: "flex",
            justifyContent:
              "space-between",
            gap: "10px",
          }}
        >
          <strong>C4:</strong>

          <span>
            {formatDate(
              displayedCircumstances.c4
            )}
          </span>
        </div>

    <hr />

    <div
      style={{
        display: "flex",
        justifyContent:
          "space-between",
        gap: "10px",
      }}
    >
      <strong>
        Altura Solar:
      </strong>

      <span>
        {displayedCircumstances.sun_alt.toFixed(
          2
        )}
        °
      </span>
    </div>

    <div
      style={{
        display: "flex",
        justifyContent:
          "space-between",
        gap: "10px",
      }}
    >
      <strong>
        Azimute Solar:
      </strong>

      <span>
        {displayedCircumstances.sun_az.toFixed(
          2
        )}
        °
      </span>
    </div>
  </>
)}
            </>
          )}
        </div>
      </div>
    </div>
  );
}
