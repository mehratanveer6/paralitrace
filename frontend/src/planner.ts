import type { Plan, PlanInputs } from './types';

/** Stable sort of indices by key, descending (mirrors numpy argsort(-key, kind="stable")). */
function orderDesc(n: number, key: (i: number) => number): number[] {
  return Array.from({ length: n }, (_, i) => i).sort((a, b) => key(b) - key(a) || a - b);
}

const round = (x: number, d: number) => Math.round(x * 10 ** d) / 10 ** d;

/**
 * Browser copy of plan_interventions in paralitrace/model/analysis.py, for the hosted demo where
 * there is no Python server. Same greedy ratio rule, same biggest-fires baseline, same output.
 */
export function planLocal(pi: PlanInputs, budget: number): Plan {
  const cl = pi.clusters;
  const preventable = cl.reduce((s, c) => s + c.harm, 0);
  const chosen: Plan['clusters'] = [];
  let spent = 0, gained = 0;
  for (const i of orderDesc(cl.length, i => cl[i].harm / cl[i].cost)) {
    const c = cl[i];
    if (c.harm <= 0) break;
    if (spent + c.cost > budget) continue;
    spent += c.cost; gained += c.harm;
    chosen.push({
      cluster_id: c.id, lat: c.lat!, lon: c.lon!, location: c.location!, fires: c.fires!, frp_mw: c.frp_mw!,
      share_of_preventable_pct: preventable ? round((100 * c.harm) / preventable, 2) : 0,
      protects: c.protects ?? [],
    });
  }
  let naive = 0, spentN = 0;
  for (const i of orderDesc(cl.length, i => cl[i].frp)) {
    if (spentN + cl[i].cost > budget) continue;
    spentN += cl[i].cost; naive += cl[i].harm;
  }
  return {
    budget_fires: budget,
    fires_targeted: spent,
    clusters: chosen,
    exposure_avoided_pct_of_preventable: preventable ? round((100 * gained) / preventable, 1) : 0,
    exposure_avoided_pct_of_total: pi.total_harm ? round((100 * gained) / pi.total_harm, 1) : 0,
    naive_biggest_fires_pct_of_preventable: preventable ? round((100 * naive) / preventable, 1) : 0,
    note: "Benefit counts only tomorrow's projected burning; smoke already emitted cannot be prevented.",
  };
}
