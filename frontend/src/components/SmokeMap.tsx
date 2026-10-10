import { useEffect, useMemo, useRef } from 'react';
import L from 'leaflet';
import { CircleMarker, MapContainer, Polyline, TileLayer, Tooltip, useMap } from 'react-leaflet';
import { INK, LEFT_LABEL, band, hourAt, plural } from '../lib';
import type { City, Cluster, Counterfactual, Forecast, Plan, Snapshot, Wind } from '../types';

/** Punjab, Haryana and Delhi NCR: the map opens fitted to this, whatever the screen size. */
const REGION: L.LatLngBoundsExpression = [[28.3, 73.9], [32.0, 77.6]];

/** Draw order, bottom to top. Each pane gets its own canvas. */
const PANES: [string, number][] = [
  ['wind', 410], ['smoke', 420], ['fires', 430], ['plan', 440], ['links', 450], ['cities', 460],
];

function Panes() {
  const map = useMap();
  // Created synchronously on first render so sibling layers can target them.
  for (const [name, z] of PANES) {
    if (!map.getPane(name)) map.createPane(name).style.zIndex = String(z);
  }
  return null;
}

/** A Leaflet layer group on its own canvas renderer, for layers redrawn imperatively every frame. */
function useCanvasGroup(pane: string) {
  const map = useMap();
  const renderer = useMemo(() => L.canvas({ pane, padding: 0.3 }), [pane]);
  const group = useRef<L.LayerGroup | null>(null);
  if (!group.current) group.current = L.layerGroup();
  useEffect(() => {
    const g = group.current!;
    g.addTo(map);
    return () => { g.remove(); };
  }, [map]);
  return { group: group.current, renderer };
}

function WindLayer({ wind, t }: { wind: Wind; t: number }) {
  const { group, renderer } = useCanvasGroup('wind');
  useEffect(() => {
    group.clearLayers();
    let k = 0;
    wind.times.forEach((wt, i) => { if (Math.abs(wt - t) < Math.abs(wind.times[k] - t)) k = i; });
    const s = 0.06;
    wind.lats.forEach((la, yi) => wind.lons.forEach((lo, xi) => {
      const u = wind.u[k][yi][xi], v = wind.v[k][yi][xi];
      const tip: L.LatLngTuple = [la + v * s, lo + (u * s) / Math.cos((la * Math.PI) / 180)];
      L.polyline([[la, lo], tip],
        { renderer, pane: 'wind', color: '#000', weight: 1.5, opacity: 0.35, dashArray: '2 3', interactive: false }).addTo(group);
      // solid dot marks the downwind end, so direction reads at a glance
      L.circleMarker(tip, { renderer, pane: 'wind', radius: 2, stroke: false, fillColor: '#000', fillOpacity: 0.5, interactive: false }).addTo(group);
    }));
  }, [group, renderer, wind, t]);
  return null;
}

/** Smoke particles as halftone dots: dot size encodes density, ink stays flat. */
function SmokeLayer({ snap, massRef }: { snap: Snapshot; massRef: number }) {
  const { group, renderer } = useCanvasGroup('smoke');
  useEffect(() => {
    group.clearLayers();
    for (const [la, lo, m] of snap.points) {
      L.circleMarker([la, lo], { renderer, pane: 'smoke', interactive: false, stroke: false,
        radius: 1.2 + 4.5 * Math.min(1, Math.sqrt(m / massRef)), fillColor: '#000', fillOpacity: 0.55 }).addTo(group);
    }
  }, [group, renderer, snap, massRef]);
  return null;
}

/** Fire clusters in fluorescent orange over a black pass offset by 3 px, like a slipped print plate. */
function FiresLayer({ clusters }: { clusters: Cluster[] }) {
  const map = useMap();
  const { group, renderer } = useCanvasGroup('fires');
  useEffect(() => {
    group.clearLayers();
    const shadows: [L.CircleMarker, L.LatLng][] = [];
    for (const c of clusters) {
      const r = 2.5 + Math.sqrt(c.frp_mw) / 3;
      const ll = L.latLng(c.lat, c.lon);
      const sh = L.circleMarker(ll, { renderer, pane: 'fires', radius: r, stroke: false, fillColor: '#000', fillOpacity: 0.85, interactive: false }).addTo(group);
      shadows.push([sh, ll]);
      L.circleMarker(ll, { renderer, pane: 'fires', radius: r, stroke: false, fillColor: '#ff5f1f', fillOpacity: 1 })
        .bindTooltip(`${plural(c.n_fires, 'fire')}, ${c.frp_mw.toFixed(0)} MW`).addTo(group);
    }
    const shift = () => shadows.forEach(([m, ll]) => m.setLatLng(map.layerPointToLatLng(map.latLngToLayerPoint(ll).add([3, 3]))));
    shift();
    map.on('zoomend', shift);
    return () => { map.off('zoomend', shift); };
  }, [group, renderer, clusters, map]);
  return null;
}

function FlyTo({ city }: { city: City | null }) {
  const map = useMap();
  useEffect(() => { if (city) map.flyTo([city.lat, city.lon], 8, { duration: 0.6 }); }, [city, map]);
  return null;
}

interface Props {
  data: Forecast;
  frame: number;
  city: City | null;
  plan: Plan | null;
  /** When set, draw the forecast with the plan's fires stopped. */
  after: Counterfactual | null;
  onSelectCity: (id: string) => void;
}

export function SmokeMap({ data, frame, city, plan, after, onSelectCity }: Props) {
  const snap = (after?.plumes[frame]) ?? data.plumes[frame];
  const afterIndex = useMemo(() => new Map(after?.cities.map(c => [c.id, c.hourly_index]) ?? []), [after]);
  const h = hourAt(data, frame);
  // 95th percentile particle mass sets the halftone scale for the whole run
  const massRef = useMemo(() => {
    const m = data.plumes.flatMap(f => f.points.map(p => p[2])).sort((a, b) => a - b);
    return m[Math.floor(m.length * 0.95)] || 1;
  }, [data]);

  return (
    <MapContainer className="map" bounds={REGION} boundsOptions={{ padding: [24, 24] }} zoomSnap={0.25} preferCanvas>
      <Panes />
      {/* Esri's label-free grey canvas needs no key; the print filter in styles.css flattens it further. */}
      <TileLayer url="https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Light_Gray_Base/MapServer/tile/{z}/{y}/{x}"
        attribution="Tiles &copy; Esri, HERE, Garmin, &copy; OpenStreetMap contributors" maxZoom={12} />
      <WindLayer wind={data.wind} t={snap.t} />
      <SmokeLayer snap={snap} massRef={massRef} />
      <FiresLayer clusters={data.clusters} />

      {plan?.clusters.map(c => (
        <CircleMarker key={c.cluster_id} pane="plan" center={[c.lat, c.lon]} radius={11}
          pathOptions={after
            ? { color: '#000', weight: 2, fill: true, fillColor: '#00a95c', fillOpacity: 1 }   // stopped: field is out
            : { color: '#00a95c', weight: 4, fill: false }}>
          <Tooltip>{plural(c.fires, 'fire')}, {c.location}</Tooltip>
        </CircleMarker>
      ))}

      {city?.top_sources.map(s => (
        <Polyline key={`${city.id}-${s.area}`} pane="links" positions={[[s.lat, s.lon], [city.lat, city.lon]]}
          pathOptions={{ color: '#000', weight: 3, dashArray: '1 7', lineCap: 'round' }} />
      ))}

      {data.cities.map(c => {
        const left = LEFT_LABEL.has(c.id);
        return (
          <CircleMarker key={c.id} pane="cities" center={[c.lat, c.lon]} radius={9}
            pathOptions={{ color: '#000', weight: 3, fillOpacity: 1, fillColor: INK[band((afterIndex.get(c.id) ?? c.hourly_index)[h] ?? 0)] }}
            eventHandlers={{ click: () => onSelectCity(c.id) }}>
            <Tooltip permanent className="cl" direction={left ? 'left' : 'right'} offset={[left ? -10 : 10, 0]}>{c.name}</Tooltip>
          </CircleMarker>
        );
      })}

      <FlyTo city={city} />
    </MapContainer>
  );
}
