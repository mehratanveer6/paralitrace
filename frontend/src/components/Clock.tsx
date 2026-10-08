import { fmt, hourAt } from '../lib';
import type { Forecast } from '../types';

export function Clock({ data, frame }: { data: Forecast; frame: number }) {
  const snap = data.plumes[frame];
  const h = hourAt(data, frame);
  return (
    <div className="clock">
      <div className="when">{fmt(snap.t, { weekday: 'short', hour: '2-digit', minute: '2-digit' })} IST</div>
      <div className="rel">{h === 0 ? 'Now' : `${h} hours from now`}</div>
      {data.meta.mode !== 'live' && <div className="demo">Demo data, not real fires</div>}
    </div>
  );
}
