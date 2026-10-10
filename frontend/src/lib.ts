import type { Backtest, City, Forecast, Plan, Risk, ToolCall } from './types';

/** Smoke-index thresholds, kept in sync with RISK_BANDS in paralitrace/config.py. */
export const RISK: [number, Risk][] = [[0, 'low'], [20, 'moderate'], [60, 'high'], [150, 'severe']];

/** Risograph inks per risk level. */
export const INK: Record<Risk, string> = {
  low: '#d4d2ca', moderate: '#ffe800', high: '#ff5f1f', severe: '#ff3ea5',
};

export const band = (v: number): Risk => RISK.reduce<Risk>((b, [t, n]) => (v >= t ? n : b), 'low');

export const plural = (n: number, w: string) => `${n} ${w}${n === 1 ? '' : 's'}`;

export const fmt = (epoch: number, o: Intl.DateTimeFormatOptions) =>
  new Date(epoch * 1000).toLocaleString('en-IN', { timeZone: 'Asia/Kolkata', hour12: false, ...o });

/** Cities whose map labels sit on the left to avoid collisions with neighbours. */
export const LEFT_LABEL = new Set(['mohali', 'gurugram', 'rohtak', 'patiala', 'sonipat']);

export const hourAt = (d: Forecast, frame: number) =>
  Math.round((d.plumes[frame].t - d.meta.forecast_start_epoch) / 3600);

export const worstAt = (d: Forecast, h: number) => Math.max(...d.cities.map(c => c.hourly_index[h] ?? 0));

export const hoursToPeak = (c: City) => c.hourly_index.indexOf(Math.max(...c.hourly_index));

async function json<T>(r: Response): Promise<T> {
  const body = await r.json();
  if (!r.ok) throw new Error(body?.detail ?? `Request failed (${r.status})`);
  return body as T;
}

export const api = {
  latest: () => fetch('/api/latest').then(r => json<Forecast>(r)),
  /** Resolves to null when no backtest has been run yet (404). */
  backtest: () => fetch('/api/backtest').then(r => (r.status === 404 ? null : json<Backtest>(r))),
  run: (mode: 'live' | 'synthetic') =>
    fetch('/api/run', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ mode }),
    }).then(r => json<unknown>(r)),
  plan: (budget: number) => fetch(`/api/plan?budget=${budget}`).then(r => json<Plan>(r)),
  ask: (question: string) =>
    fetch('/api/ask', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ question }),
    }).then(r => json<{ answer: string; tools?: ToolCall[] }>(r)),
};
