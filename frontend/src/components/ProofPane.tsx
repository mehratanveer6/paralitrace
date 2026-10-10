import { useEffect, useMemo, useState } from 'react';
import { api } from '../lib';
import type { Backtest, BacktestDay, Heldout } from '../types';

const W = 340, H = 150, ROWS = 22; // chart area + two tick rows for spikes

/** Season chart: forecast index (halftone area) against measured PM2.5 (line), each on its own scale. */
function SeasonChart({ days }: { days: BacktestDay[] }) {
  const n = days.length;
  if (n < 2) return null;
  const x = (i: number) => (i * W) / (n - 1);
  const pMax = Math.max(...days.map(d => d.predicted_index), 1);
  const oVals = days.map(d => d.observed_pm25).filter((v): v is number => v != null);
  const oMax = Math.max(...oVals, 1);
  const yP = (v: number) => H - 4 - ((H - 12) * v) / pMax;
  const yO = (v: number) => H - 4 - ((H - 12) * v) / oMax;

  const area = `M0,${H - 4} ` + days.map((d, i) => `L${x(i)},${yP(d.predicted_index)}`).join(' ') + ` L${W},${H - 4} Z`;
  // break the line where the monitor had no data
  let line = '', pen = false;
  days.forEach((d, i) => {
    if (d.observed_pm25 == null) { pen = false; return; }
    line += `${pen ? 'L' : 'M'}${x(i)},${yO(d.observed_pm25)} `; pen = true;
  });
  const bw = Math.max(2, W / n - 1);

  return (
    <svg className="spark season" viewBox={`0 0 ${W} ${H + ROWS}`} preserveAspectRatio="none" role="img"
      aria-label="Forecast smoke index and measured PM2.5 across the season">
      <defs>
        <pattern id="ht2" width="5" height="5" patternUnits="userSpaceOnUse">
          <circle cx="2.5" cy="2.5" r="1.5" fill="#ff5f1f" />
        </pattern>
      </defs>
      <path d={area} fill="url(#ht2)" stroke="#ff5f1f" strokeWidth={1.5} />
      <path d={line} fill="none" stroke="#000" strokeWidth={2.2} />
      <line x1={0} x2={W} y1={H} y2={H} stroke="#000" strokeWidth={1} />
      {days.map((d, i) => d.predicted_spike &&
        <rect key={`p${i}`} x={x(i) - bw / 2} y={H + 3} width={bw} height={7} fill="#ff5f1f" />)}
      {days.map((d, i) => d.observed_spike &&
        <rect key={`o${i}`} x={x(i) - bw / 2} y={H + 12} width={bw} height={7} fill="#ff3ea5" />)}
    </svg>
  );
}

const ORDER = ['persistence', 'smoke_only', 'combined', 'autogluon_no_smoke', 'autogluon', 'autogluon_combined',
  'calibrated_no_smoke', 'calibrated'];
const NAME: Record<string, string> = {
  persistence: "Repeat yesterday's reading",
  smoke_only: 'ParaliTrace smoke model',
  combined: "Yesterday's rule + ParaliTrace alerts",
  calibrated_no_smoke: 'Regression on yesterday (tried)',
  calibrated: 'Regression on yesterday + smoke (tried)',
  autogluon_no_smoke: 'AutoGluon on PM2.5 history',
  autogluon: 'AutoGluon with smoke model input',
  autogluon_combined: 'AutoGluon forecast + ParaliTrace alerts',
};

const PHRASE: Record<string, string> = {
  smoke_only: 'the ParaliTrace smoke model',
  combined: "yesterday's rule plus ParaliTrace's alerts",
  autogluon_combined: "an AutoGluon forecast plus ParaliTrace's alerts",
};

function HeldoutBlock({ h }: { h: Heldout }) {
  const methods = [...h.methods].sort((a, b) => ORDER.indexOf(a.key) - ORDER.indexOf(b.key));
  const base = methods.find(x => x.key === 'persistence')!;
  // best: most spike days caught, then most new spells, then fewest false alarms
  const best = methods.filter(x => x.key !== 'persistence')
    .sort((a, b) => b.caught - a.caught || b.onsets_caught - a.onsets_caught || a.false_alarm_pct - b.false_alarm_pct)[0];
  const smoke = methods.find(x => x.key === 'smoke_only');
  const beats = best && best.caught > base.caught;
  return (
    <>
      <h3>Tested on days it never saw</h3>
      <p className="note">Scored only on {h.test}: no setting was tuned on it, and every forecast used only data from
        before the day it forecast. {h.spike_days} spike days, {h.onset_days} of them the first smoky day of a new spell.</p>
      {beats ? (
        <div className="vs">
          <div className="win"><span className="big">{best.caught}/{h.spike_days}</span>spike days caught a day ahead with {PHRASE[best.key] ?? NAME[best.key]}, {best.onsets_caught} of {h.onset_days} new spells</div>
          <div className="lose"><span className="big">{base.caught}/{h.spike_days}</span>by repeating yesterday's reading, {base.onsets_caught} new spells</div>
        </div>
      ) : smoke && (
        <div className="vs">
          <div className="win"><span className="big">{smoke.onsets_caught}/{h.onset_days}</span>new smoky spells seen coming a day ahead by the smoke model</div>
          <div className="lose"><span className="big">0/{h.onset_days}</span>by repeating yesterday's reading</div>
        </div>
      )}
      <table className="bt">
        <thead><tr><th>Method</th><th>Caught</th><th>New spells</th><th>False alarms</th><th>Error</th></tr></thead>
        <tbody>
          {methods.map(x => (
            <tr key={x.key} aria-selected={beats && x.key === best.key}>
              <td>{NAME[x.key] ?? x.label}</td><td>{x.caught}</td><td>{x.onsets_caught}</td><td>{x.false_alarm_pct}%</td>
              <td>{x.mae != null ? `${x.mae} µg/m³` : 'n/a'}</td>
            </tr>
          ))}
        </tbody>
      </table>
      <p className="note">Repeating yesterday can't catch a new spell by definition; only the smoke model can see one coming.
        Combined rules raise an alert when either part does. AutoGluon (AWS's open-source AutoML) learns a PM2.5
        forecast from each city's history, retrained every day on everything before it. Error is the average miss in
        daily PM2.5 where a method predicts a number. A two-term regression was also tried and didn't beat the simple
        rules. Every method is scored on the same days.</p>
    </>
  );
}

export function ProofPane() {
  const [bt, setBt] = useState<Backtest | null | undefined>(undefined);
  const [error, setError] = useState<string | null>(null);
  const [cityId, setCityId] = useState<string>('');

  useEffect(() => {
    api.backtest().then(b => {
      setBt(b);
      if (b?.cities.length) setCityId([...b.cities].sort((a, c) => c.spike_days - a.spike_days)[0].id);
    }).catch(e => setError((e as Error).message));
  }, []);

  const city = useMemo(() => bt?.cities.find(c => c.id === cityId), [bt, cityId]);

  if (error) return <div className="err">Could not load the backtest: {error}</div>;
  if (bt === undefined) return <p className="note">Loading</p>;
  if (bt === null) {
    return (
      <>
        <h3>Did past forecasts come true?</h3>
        <p className="note">No backtest yet. When it runs, this replays a past burning season day by day:
          each day's smoke is forecast 24 hours ahead and checked against what air-quality monitors measured.</p>
      </>
    );
  }

  const s = bt.summary;
  return (
    <>
      <h3>Did past forecasts come true?</h3>
      <p className="note">{bt.season}, forecasts made {bt.lead_hours} hours ahead and checked against ground monitors. {bt.spike_definition}</p>

      {bt.heldout && <HeldoutBlock h={bt.heldout} />}

      <h3>The whole season, smoke model alone</h3>
      {s.onset_days != null && s.onsets_caught != null && s.onset_days > 0 ? (
        <div className="vs">
          <div className="win"><span className="big">{s.onsets_caught}/{s.onset_days}</span>smoky spells seen coming a day ahead, from fires and wind alone</div>
          <div className="lose"><span className="big">0/{s.onset_days}</span>by {s.baseline_label}, which can only follow a spell once it starts</div>
        </div>
      ) : (
        <div className="vs">
          <div className="win"><span className="big">{s.spikes_caught}/{s.spike_days}</span>smoke spike days caught a day ahead ({s.hit_rate_pct}%)</div>
          <div className="lose"><span className="big">{s.baseline_hit_rate_pct}%</span>caught by {s.baseline_label}</div>
        </div>
      )}
      <p className="note">
        Across all {s.spike_days} spike days it caught {s.spikes_caught} ({s.hit_rate_pct}%), against {s.baseline_hit_rate_pct}% for {s.baseline_label}.
        {' '}{s.false_alarm_pct}% of predicted spikes did not happen.
        {s.median_correlation != null && <> Median rank correlation with measured PM2.5: {s.median_correlation.toFixed(2)}.</>}
      </p>

      <label htmlFor="btcity">City</label>
      <select id="btcity" value={cityId} onChange={e => setCityId(e.target.value)}>
        {[...bt.cities].sort((a, c) => c.spike_days - a.spike_days).map(c =>
          <option key={c.id} value={c.id}>{c.name}</option>)}
      </select>

      {city && (
        <>
          <SeasonChart days={city.days} />
          <div className="axis"><span>{bt.start}</span><span>{bt.end}</span></div>
          <div className="chart-key">
            <span><i className="k-line" />Measured PM2.5</span>
            <span><i className="k-area" />Forecast smoke</span>
            <span><i className="k-tick" style={{ background: 'var(--fire)' }} />Spike forecast</span>
            <span><i className="k-tick" style={{ background: 'var(--severe)' }} />Spike happened</span>
          </div>
          <p className="note">{city.name}: caught {city.spikes_caught} of {city.spike_days} spike days, {city.false_alarms} false {city.false_alarms === 1 ? 'alarm' : 'alarms'}
            {city.correlation != null && <>, rank correlation {city.correlation.toFixed(2)}</>}. Each line is scaled to its own maximum.</p>
        </>
      )}

      {bt.notes && <p className="note">{bt.notes}</p>}

      <h3>Every city</h3>
      <table className="bt">
        <thead><tr><th>City</th><th>Caught</th><th>False alarms</th><th>Correlation</th></tr></thead>
        <tbody>
          {bt.cities.map(c => (
            <tr key={c.id} aria-selected={c.id === cityId} onClick={() => setCityId(c.id)}>
              <td>{c.name}</td>
              <td>{c.spikes_caught}/{c.spike_days}</td>
              <td>{c.false_alarms}</td>
              <td>{c.correlation != null ? c.correlation.toFixed(2) : 'n/a'}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </>
  );
}
