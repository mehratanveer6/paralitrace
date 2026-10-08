import type { ReactNode } from 'react';
import type { Forecast } from '../types';

function bulletin(data: Forecast): ReactNode[] {
  const items: ReactNode[] = [...data.cities]
    .filter(c => c.peak_risk !== 'low')
    .sort((a, b) => b.peak_index - a.peak_index)
    .slice(0, 8)
    .map(c => <>{c.name}: smoke peaks <b className={c.peak_risk === 'severe' ? 'sev' : ''}>{c.peak_risk}</b> around {c.peak_time_ist}</>);
  const p = data.plan;
  items.push(<>Stopping {p.fires_targeted} fires in the right places cuts tomorrow's preventable exposure by <b>{p.exposure_avoided_pct_of_preventable}%</b></>);
  if (data.meta.mode !== 'live') items.unshift(<><b>Demo data</b> on screen</>);
  return items;
}

export function Masthead({ data }: { data: Forecast }) {
  const items = bulletin(data);
  return (
    <header className="mast">
      <div className="brand">
        <span className="gur" lang="pa" aria-hidden="true">ਪਰਾਲੀ</span>
        <div>
          <h1>ParaliTrace</h1>
          <p>Follow the stubble smoke. Stop the right fires.</p>
        </div>
      </div>
      <div className="ticker" aria-label="Smoke bulletin">
        <div className="ticker-track">
          {items.map((it, i) => <span key={i}>{it}</span>)}
          {/* second copy makes the crawl loop seamlessly */}
          {items.map((it, i) => <span key={`dup${i}`} aria-hidden="true">{it}</span>)}
        </div>
      </div>
    </header>
  );
}
