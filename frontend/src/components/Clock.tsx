import { useState } from 'react';
import { api, fmt, hourAt } from '../lib';
import type { Forecast } from '../types';

interface Props { data: Forecast; frame: number; onRefreshed: () => Promise<void> }

export function Clock({ data, frame, onRefreshed }: Props) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const snap = data.plumes[frame];
  const h = hourAt(data, frame);
  const live = data.meta.mode === 'live';
  const updated = fmt(Date.parse(data.meta.generated_utc) / 1000, { weekday: 'short', hour: '2-digit', minute: '2-digit' });

  const fetchLive = async () => {
    setBusy(true); setError(null);
    try { await api.run('live'); await onRefreshed(); }
    catch (e) { setError((e as Error).message); }
    setBusy(false);
  };

  return (
    <div className="clock">
      <div className="when">{fmt(snap.t, { weekday: 'short', hour: '2-digit', minute: '2-digit' })} IST</div>
      <div className="rel">{h === 0 ? 'Now' : `${h} hours from now`}</div>
      <div className="src">
        {live
          ? <span className="live">Live satellite fires</span>
          : <span className="demo">Demo data, not real fires</span>}
        <button className="link" onClick={fetchLive} disabled={busy}>
          {busy ? 'Fetching fires and winds' : live ? 'Refresh' : 'Fetch live fires'}
        </button>
      </div>
      <div className="note">Forecast made {updated} IST</div>
      {error && <div className="err">{error}</div>}
    </div>
  );
}
