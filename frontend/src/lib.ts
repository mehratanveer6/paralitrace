import type { Backtest, City, Forecast, Plan, Risk, ToolCall } from './types';
import { planLocal } from './planner';

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

/* Two ways to run:
 * - Local / server: FastAPI answers /api/*.
 * - Hosted demo (e.g. Vercel): no Python server, so the app reads a snapshot from /demo/*.json,
 *   re-plans in the browser and shows recorded answers. Detected at load: /api/latest doesn't return JSON.
 */
let hosted = false;
let snapshot: Forecast | null = null;
export const isHosted = () => hosted;

async function maybeJson(url: string): Promise<unknown | null> {
  try {
    const r = await fetch(url);
    if (!r.ok || !(r.headers.get('content-type') ?? '').includes('json')) return null;
    return await r.json();
  } catch { return null; }
}

interface Recorded { question: string; answer: string; tools: ToolCall[]; model?: string }

export const api = {
  latest: async (): Promise<Forecast> => {
    const live = await maybeJson('/api/latest');
    if (live) { hosted = false; return live as Forecast; }
    const snap = await maybeJson('/demo/latest.json');
    if (!snap) throw new Error('No forecast available');
    hosted = true; snapshot = snap as Forecast;
    return snapshot;
  },
  /** Resolves to null when no backtest has been run yet. */
  backtest: async (): Promise<Backtest | null> => {
    if (hosted) return (await maybeJson('/demo/backtest.json')) as Backtest | null;
    return fetch('/api/backtest').then(r => (r.status === 404 ? null : json<Backtest>(r)));
  },
  run: (mode: 'live' | 'synthetic') => {
    if (hosted) return Promise.reject(new Error('Live refresh runs on the full app; this hosted demo shows a fixed snapshot.'));
    return fetch('/api/run', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ mode }),
    }).then(r => json<unknown>(r));
  },
  plan: async (budget: number): Promise<Plan> => {
    if (hosted && snapshot?.plan_inputs) return planLocal(snapshot.plan_inputs, budget);
    return fetch(`/api/plan?budget=${budget}`).then(r => json<Plan>(r));
  },
  ask: async (question: string): Promise<{ answer: string; tools?: ToolCall[]; model?: string; recorded?: boolean }> => {
    if (hosted) {
      const rec = ((await maybeJson('/demo/answers.json')) as Recorded[] | null) ?? [];
      const hit = rec.find(r => r.question.trim().toLowerCase() === question.trim().toLowerCase());
      if (hit) return { answer: hit.answer, tools: hit.tools, model: hit.model, recorded: true };
      throw new Error('In this hosted demo the assistant shows recorded answers to the three example questions. '
        + 'Free-form questions need the full app, which calls the model with a private key.');
    }
    return fetch('/api/ask', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ question }),
    }).then(r => json<{ answer: string; tools?: ToolCall[]; model?: string }>(r));
  },
};
