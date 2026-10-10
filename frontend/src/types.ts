// Shapes of the JSON served by the FastAPI backend (paralitrace/pipeline.py).

export type Risk = 'low' | 'moderate' | 'high' | 'severe';
export type Tab = 'cities' | 'plan' | 'ask' | 'proof';

export interface Meta {
  mode: 'synthetic' | 'live' | 'replay';
  replay_date?: string | null;   // YYYY-MM-DD when mode is 'replay'
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

/* ---- Backtest: output/backtest.json, served at /api/backtest ----
 * A past season replayed day by day: forecast each day's smoke 24 h ahead from the previous
 * day's fires and archived winds, then compare with PM2.5 measured at ground monitors.
 */

export interface BacktestDay {
  date: string;                   // YYYY-MM-DD (IST)
  predicted_index: number;        // forecast smoke index, made 24 h ahead
  observed_pm25: number | null;   // daily mean PM2.5, µg/m³; null when the monitor had no data
  observed_spike: boolean;        // the city had a smoke spike that day
  predicted_spike: boolean;       // the forecast called a spike
}

export interface BacktestCity {
  id: string;
  name: string;
  spike_days: number;
  spikes_caught: number;
  false_alarms: number;
  correlation: number | null;     // Spearman, predicted index vs observed PM2.5
  days: BacktestDay[];
}

export interface HeldoutMethod {
  key: 'persistence' | 'smoke_only' | 'calibrated_no_smoke' | 'calibrated';
  label: string;
  caught: number;
  false_alarm_pct: number;
  onsets_caught: number;
  mae: number | null;           // mean absolute error in PM2.5, µg/m³
}

/** Calibrated forecast trained on the first part of the season, scored only on the rest. */
export interface Heldout {
  train: string;
  test: string;
  test_city_days: number;
  spike_days: number;
  onset_days: number;
  methods: HeldoutMethod[];
}

export interface Backtest {
  season: string;                 // e.g. "Oct-Nov 2025"
  start: string;
  end: string;
  lead_hours: number;             // 24
  spike_definition: string;       // plain words, shown in the UI
  notes?: string;                 // method caveats, shown under the chart
  summary: {
    spike_days: number;           // across all cities
    spikes_caught: number;
    hit_rate_pct: number;
    false_alarm_pct: number;      // share of predicted spikes that did not happen
    median_correlation: number | null;
    baseline_label: string;       // e.g. "yesterday's PM2.5 repeated"
    baseline_hit_rate_pct: number;
    onset_days?: number;          // first day of each spike episode, which "repeat yesterday" can never catch
    onsets_caught?: number;
  };
  heldout?: Heldout | null;
  cities: BacktestCity[];
}

export interface CounterfactualCity {
  id: string;
  name: string;
  hourly_index: number[];
  before_peak_risk: Risk;
  after_peak_risk: Risk;
  reduction_pct: number;
}

/** The same forecast with the default plan's fires stopped. */
export interface Counterfactual {
  budget_fires: number;
  plumes: Snapshot[];
  cities: CounterfactualCity[];
}

export interface ToolCall { name: string; input: Record<string, unknown> }

export interface Forecast {
  meta: Meta;
  clusters: Cluster[];
  cities: City[];
  plan: Plan;
  counterfactual?: Counterfactual;
  plumes: Snapshot[];
  wind: Wind;
}
