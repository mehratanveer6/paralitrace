// Shapes of the JSON served by the FastAPI backend (paralitrace/pipeline.py).

export type Risk = 'low' | 'moderate' | 'high' | 'severe';
export type Tab = 'cities' | 'plan' | 'ask';

export interface Meta {
  mode: 'synthetic' | 'live';
  data_label: string;
  generated_utc: string;
  forecast_start_epoch: number;
  horizon_hours: number;
  fire_detections: number;
  clusters: number;
  runtime_s: number | null;
  calibrated: boolean;
}

export interface Cluster {
  id: string;
  lat: number;
  lon: number;
  frp_mw: number;
  n_fires: number;
  t_epoch: number;
}

export interface Source {
  area: string;
  lat: number;
  lon: number;
  share_pct: number;
  fires: number;
  distance_km: number;
}

export interface City {
  id: string;
  name: string;
  lat: number;
  lon: number;
  population: number;
  hourly_index: number[];
  day1_mean: number;
  day2_mean: number;
  peak_index: number;
  peak_time_ist: string | null;
  day1_risk: Risk;
  day2_risk: Risk;
  peak_risk: Risk;
  preventable_pct: number;
  top_sources: Source[];
}

export interface PlanCluster {
  cluster_id: string;
  lat: number;
  lon: number;
  location: string;
  fires: number;
  frp_mw: number;
  share_of_preventable_pct: number;
  protects: string[];
}

export interface Plan {
  budget_fires: number;
  fires_targeted: number;
  clusters: PlanCluster[];
  exposure_avoided_pct_of_preventable: number;
  exposure_avoided_pct_of_total: number;
  naive_biggest_fires_pct_of_preventable: number;
  note: string;
}

/** [lat, lon, relative mass] */
export type Particle = [number, number, number];

export interface Snapshot {
  t: number;
  points: Particle[];
}

export interface Wind {
  lats: number[];
  lons: number[];
  times: number[];
  u: number[][][];
  v: number[][][];
}

export interface Forecast {
  meta: Meta;
  clusters: Cluster[];
  cities: City[];
  plan: Plan;
  plumes: Snapshot[];
  wind: Wind;
}
