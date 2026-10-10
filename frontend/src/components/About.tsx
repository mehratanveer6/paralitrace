import { useRef } from 'react';

/** Method, data and limitations in one place, for anyone asking "how do you know?" */
export function About() {
  const ref = useRef<HTMLDialogElement>(null);
  return (
    <>
      <button className="link about-btn" onClick={() => ref.current?.showModal()}>How it works</button>
      <dialog ref={ref} className="about" onClick={e => { if (e.target === ref.current) ref.current?.close(); }}>
        <button className="close" onClick={() => ref.current?.close()} aria-label="Close">×</button>
        <h2>How ParaliTrace works</h2>

        <h3>Find the fires</h3>
        <p>NASA's VIIRS satellites detect every active fire across Punjab and Haryana several times a day.
          Detections are grouped into roughly 10 km cells. A cell's fire radiative power stands in for how much smoke it makes.</p>

        <h3>Follow the smoke</h3>
        <p>Each cell releases thousands of virtual smoke particles. They drift with hourly wind forecasts from Open-Meteo,
          spread with turbulence, and settle out over about two days. When particles pass within 20 km of a city,
          that city's smoke index rises, and every particle remembers which fields it came from.</p>

        <h3>Decide what to stop</h3>
        <p>Smoke already in the air can't be recalled. Fields expected to burn again tomorrow can be reached.
          The planner ranks those fields by how many people their smoke would reach, for the number of locations
          field teams can cover, and compares that against sending teams to the biggest fires.</p>

        <h3>Explain it</h3>
        <p>An assistant built with the Strands Agents SDK, AWS's open-source agent framework, answers questions and writes
          school advisories in English, Hindi or Punjabi. It reaches the forecast only through five tools, so it can only
          quote numbers the model produced.</p>

        <h3>Check it</h3>
        <p>The Proof tab replays the 2025 season against ground monitors. A forecast from AutoGluon, AWS's open-source
          AutoML library, retrained each day on the past only, is combined with the smoke model's alerts and scored on
          November, which nothing was tuned on.</p>

        <h3>Limits</h3>
        <ul>
          <li>The smoke model is two-dimensional, with no chemistry or rain. It is far simpler than research models such as HYSPLIT.</li>
          <li>The smoke index is relative. Risk levels are checked against past monitor readings in the Proof tab.</li>
          <li>Tomorrow's burning is assumed to resemble today's. Fires can't be forecast from orbit.</li>
          <li>Always confirm with the official CPCB air-quality index before acting.</li>
        </ul>
      </dialog>
    </>
  );
}
