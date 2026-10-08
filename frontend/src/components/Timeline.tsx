import { band, fmt, hourAt, worstAt } from '../lib';
import type { Forecast } from '../types';

interface Props {
  data: Forecast;
  frame: number;
  playing: boolean;
  onTogglePlay: () => void;
  onSeek: (frame: number) => void;
}

/** "Smoke barcode": one cell per 3 h snapshot, coloured by the worst city at that hour. */
export function Timeline({ data, frame, playing, onTogglePlay, onSeek }: Props) {
  return (
    <div className="strip">
      <span className="strip-label">Worst smoke anywhere, every 3 hours</span>
      <button onClick={onTogglePlay} aria-label={playing ? 'Pause' : 'Play'}>{playing ? '❚❚' : '▶'}</button>
      <div className="cells" role="group" aria-label="Forecast hours">
        {data.plumes.map((p, f) => {
          const h = hourAt(data, f);
          const b = band(worstAt(data, h));
          const day = fmt(p.t, { weekday: 'short' });
          const time = fmt(p.t, { hour: '2-digit', minute: '2-digit' });
          return (
            <button key={p.t} className={`cell ${b}`} aria-current={f === frame}
              aria-label={`${day} ${time}, worst smoke ${b}`} onClick={() => onSeek(f)}>
              <b>+{String(h).padStart(2, '0')}h</b><span>{day} {time}</span>
            </button>
          );
        })}
      </div>
    </div>
  );
}
