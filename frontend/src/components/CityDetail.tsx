import { plural } from '../lib';
import type { City } from '../types';
import { Spark } from './Spark';

interface Props { city: City; hour: number; onBack: () => void }

export function CityDetail({ city: c, hour, onBack }: Props) {
  const max = Math.max(...c.top_sources.map(s => s.share_pct), 1);
  return (
    <>
      <button className="back" onClick={onBack}>All cities</button>
      <h2>{c.name}</h2>
      <span className={`st ${c.peak_risk}`}>{c.peak_risk} peak</span> <span className="note">around {c.peak_time_ist}</span>
      <Spark series={c.hourly_index} hour={hour} />
      <div className="axis"><span>Now</span><span>+24 h</span><span>+48 h</span></div>
      <h3>Where {c.name}'s smoke comes from</h3>
      <ol className="src">
        {c.top_sources.length ? c.top_sources.map(s => (
          <li key={s.area}>
            <span className="pct">{Math.round(s.share_pct)}%</span>
            <span>
              {plural(s.fires, 'fire')} around {s.area}, {s.distance_km} km away
              <div className="bar" style={{ width: `${(100 * s.share_pct) / max}%` }} />
            </span>
          </li>
        )) : <li><span /><span>No smoke reaches this city in the next 48 hours.</span></li>}
      </ol>
      <p className="note">{c.preventable_pct}% of this smoke comes from fires expected tomorrow. That part can still be stopped.</p>
    </>
  );
}
