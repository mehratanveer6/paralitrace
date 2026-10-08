import { INK, RISK } from '../lib';

const W = 340, H = 120;

/** 48 h smoke index as a halftone area over risk-band stripes, with the current hour marked. */
export function Spark({ series, hour }: { series: number[]; hour: number }) {
  const top = Math.max(...series, 160);
  const y = (v: number) => H - 4 - ((H - 8) * v) / top;
  const x = (i: number) => (i * W) / (series.length - 1);
  const area = `M0,${H - 4} ` + series.map((v, i) => `L${x(i)},${y(v)}`).join(' ') + ` L${W},${H - 4} Z`;
  const cur = x(Math.min(hour, series.length - 1));

  return (
    <svg className="spark" viewBox={`0 0 ${W} ${H}`} preserveAspectRatio="none" role="img" aria-label="Smoke over the next 48 hours">
      {RISK.map(([t, n], i) => {
        const upper = Math.min((RISK[i + 1] ?? [top * 2])[0], top);
        return <rect key={n} x={0} width={W} y={y(upper)} height={Math.max(0, y(t) - y(upper))} fill={INK[n]} opacity={0.55} />;
      })}
      <defs>
        <pattern id="ht" width="5" height="5" patternUnits="userSpaceOnUse">
          <circle cx="2.5" cy="2.5" r="1.6" fill="#000" />
        </pattern>
      </defs>
      <path d={area} fill="url(#ht)" stroke="#000" strokeWidth={2} />
      <line x1={cur} x2={cur} y1={0} y2={H} stroke="#000" strokeWidth={3} />
    </svg>
  );
}
