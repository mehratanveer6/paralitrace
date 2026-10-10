import { useState } from 'react';
import { api, fmt, hourAt, isHosted } from '../lib';
import type { Forecast } from '../types';

interface Props { data: Forecast; frame: number; onRefreshed: () => Promise<void> }

export function Clock({ data, frame, onRefreshed }: Props) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const snap = data.plumes[frame];
  const h = hourAt(data, frame);
  const mode = data.meta.mode;
  const live = mode === 'live';
  const issued = fmt(data.meta.forecast_start_epoch, { weekday: 'short', day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' });
  const replayDay = data.meta.replay_date
    ? new Date(data.meta.replay_date + 'T00:00:00+05:30').toLocaleDateString('en-IN', { day: 'numeric', month: 'short', year: 'numeric', timeZone: 'Asia/Kolkata' })
    : '';

  const fetchLive = async () => {
    setBusy(true); setError(null);
    try { await api.run('live'); await onRefreshed(); }
    catch (e) { setError((e as Error).message); }
    setBusy(false);
  };

  return (
    <div className="clock">
      <div className="when">{fmt(snap.t, { weekday: 'short', hour: '2-digit', minute: '2-digit' })} IST</div>
      {mode === 'replay' && <div className="rel">{fmt(snap.t, { day: 'numeric', month: 'short', year: 'numeric' })}</div>}
      <div className="rel">{mode === 'replay'
        ? (h === 0 ? 'When the forecast was issued' : `${h} hours after the forecast was issued`)
        : (h === 0 ? 'Now' : `${h} hours from now`)}</div>
      <div className="src">
        {mode === 'live' && <span className="live">Live satellite fires</span>}
        {mode === 'replay' && <span className="replay">Replay: real fires, {replayDay}</span>}
        {mode === 'synthetic' && <span className="demo">Demo data, not real fires</span>}
        {isHosted()
          ? <span className="note">Hosted demo snapshot</span>
          : <button className="link" onClick={fetchLive} disabled={busy}>
              {busy ? 'Fetching fires and winds' : live ? 'Refresh' : 'Fetch live fires'}
            </button>}
      </div>
      <div className="note">Forecast issued {issued} IST</div>
      {error && <div className="err">{error}</div>}
    </div>
  );
}
