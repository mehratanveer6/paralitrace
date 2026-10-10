import { useState } from 'react';
import { api, plural } from '../lib';
import type { Plan } from '../types';

interface Props { plan: Plan | null; onPlan: (p: Plan) => void; defaultBudget: number }

export function PlanPane({ plan, onPlan, defaultBudget }: Props) {
  const [budget, setBudget] = useState(defaultBudget);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const run = async () => {
    setBusy(true); setError(null);
    try { onPlan(await api.plan(budget)); }
    catch (e) { setError((e as Error).message); }
    setBusy(false);
  };

  return (
    <>
      <h3>Which fires to stop tomorrow</h3>
      <p className="note">Teams and crop-residue machines can only reach so many fields. This picks the fires whose smoke would reach the most people.
        The starting number is a quarter of the fires whose smoke reaches a city.</p>
      <label htmlFor="budget">Fire locations your teams can cover</label>
      <div className="inline">
        <input id="budget" type="number" min={1} max={5000} value={budget}
          onChange={e => setBudget(Math.max(1, Number(e.target.value) || 1))} />
        <button className="go" onClick={run} disabled={busy}>Plan tomorrow</button>
      </div>
      {busy && <p className="note">Planning</p>}
      {error && <div className="err">Planning failed: {error}</div>}
      {plan && !busy && (
        <>
          <div className="vs">
            <div className="win"><span className="big">{plan.exposure_avoided_pct_of_preventable}%</span>of tomorrow's preventable smoke exposure avoided with this plan</div>
            <div className="lose"><span className="big">{plan.naive_biggest_fires_pct_of_preventable}%</span>if the same teams went to the biggest fires instead</div>
          </div>
          <p className="note">{plural(plan.clusters.length, 'cluster')}, {plural(plan.fires_targeted, 'fire location')}. {plan.note}</p>
          <ul className="tg">
            {plan.clusters.slice(0, 15).map(c => (
              <li key={c.cluster_id}>
                <b>{plural(c.fires, 'fire')}, {c.location}</b><br />
                Protects {c.protects.join(', ') || 'no covered city'}
              </li>
            ))}
          </ul>
        </>
      )}
    </>
  );
}
