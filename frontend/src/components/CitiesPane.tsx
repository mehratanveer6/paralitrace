import { hoursToPeak } from '../lib';
import type { Forecast } from '../types';

export function CitiesPane({ data, onSelect }: { data: Forecast; onSelect: (id: string) => void }) {
  const cities = [...data.cities].sort((a, b) => b.peak_index - a.peak_index);
  return (
    <>
      <div className="key"><span>Peak in</span><span>City, worst hour</span><span>Next 24 h / after</span></div>
      {cities.map(c => {
        const h = hoursToPeak(c);
        return (
          <button key={c.id} className="row" onClick={() => onSelect(c.id)}>
            <span className="h">{h === 0 ? 'Now' : `+${h}h`}<small>{h === 0 ? 'peaking' : 'to peak'}</small></span>
            <span className="n">{c.name}<small>{c.peak_time_ist}</small></span>
            <span className="stk">
              <span className={`st ${c.day1_risk}`}>{c.day1_risk}</span>
              <span className={`st ${c.day2_risk}`}>{c.day2_risk}</span>
            </span>
          </button>
        );
      })}
      <p className="note" style={{ marginTop: 14 }}>
        {data.meta.fire_detections} fire detections in {data.meta.clusters} clusters. Source: {data.meta.data_label}.
        Risk levels are not yet calibrated to PM2.5.
      </p>
    </>
  );
}
