import { useState } from 'react';
import { api, fmt, hourAt, isHosted } from '../lib';
import type { Forecast } from '../types';

interface Props { data: Forecast; frame: number; onRefreshed: () => Promise<void> }

const longDate = (iso: string) =>
  new Date(iso + 'T00:00:00+05:30').toLocaleDateString('en-IN', { day: 'numeric', month: 'long', year: 'numeric', timeZone: 'Asia/Kolkata' });

export function Clock({ data, frame, onRefreshed }: Props) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const snap = data.plumes[frame];
  const h = hourAt(data, frame);
  const mode = data.meta.mode;
  const issued = fmt(data.meta.forecast_start_epoch, { day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' });

  const fetchLive = async () => {
    setBusy(true); setError(null);
    try { await api.run('live'); await onRefreshed(); }
    catch (e) { setError((e as Error).message); }
    setBusy(false);
  };

  return (
    <div className="clock">
      {mode === 'replay' && data.meta.replay_date && (
        <div className="src"><span className="replay">Replay of {longDate(data.meta.replay_date)}</span></div>
      )}
      {mode === 'live' && <div className="src"><span className="live">Live: today's satellite fires</span></div>}
      {mode === 'synthetic' && <div className="src"><span className="demo">Demo data, not real fires</span></div>}

      {/* the time shown on the map, which moves as the timeline plays */}
      <div className="when">{fmt(snap.t, { weekday: 'short', day: 'numeric', month: 'short' })}, {fmt(snap.t, { hour: '2-digit', minute: '2-digit' })}</div>
      <div className="rel">
        IST, {mode === 'replay'
          ? (h === 0 ? 'when the forecast was issued' : `${h} hours after the forecast was issued`)
          : (h === 0 ? 'now' : `${h} hours from now`)}
      </div>

      <div className="note">
        {mode === 'replay'
          ? <>Real NASA fire detections from that day, forecast exactly as it would have been at {issued} the evening before. Not today's data.</>
          : <>Forecast issued {issued} IST.</>}
        {' '}
        {isHosted()
          ? <>Hosted demo snapshot.</>
          : <button className="link" onClick={fetchLive} disabled={busy}>
              {busy ? 'Fetching today\'s fires and winds' : mode === 'live' ? 'Refresh' : 'Switch to today\'s fires'}
            </button>}
      </div>
      {error && <div className="err">{error}</div>}
    </div>
  );
}
