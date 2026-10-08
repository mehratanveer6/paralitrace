import { useCallback, useEffect, useState } from 'react';
import { api, hourAt } from './lib';
import type { Forecast, Plan, Tab } from './types';
import { Masthead } from './components/Masthead';
import { Clock } from './components/Clock';
import { CitiesPane } from './components/CitiesPane';
import { CityDetail } from './components/CityDetail';
import { PlanPane } from './components/PlanPane';
import { AskPane } from './components/AskPane';
import { ProofPane } from './components/ProofPane';
import { SmokeMap } from './components/SmokeMap';
import { Timeline } from './components/Timeline';

const TABS: Tab[] = ['cities', 'plan', 'ask', 'proof'];
const LABEL: Record<Tab, string> = { cities: 'Cities', plan: 'Plan', ask: 'Ask', proof: 'Proof' };

const typing = (el: EventTarget | null) =>
  el instanceof HTMLElement && (el.closest('input, textarea, select, button, dialog') != null || el.isContentEditable);

export default function App() {
  const [data, setData] = useState<Forecast | null>(null);
  const [failed, setFailed] = useState(false);
  const [frame, setFrame] = useState(0);
  const [playing, setPlaying] = useState(false);
  const [tab, setTab] = useState<Tab>('cities');
  const [cityId, setCityId] = useState<string | null>(null);
  const [plan, setPlan] = useState<Plan | null>(null);

  const reload = useCallback(async () => {
    const d = await api.latest();
    setData(d);
    setFrame(f => Math.min(f, d.plumes.length - 1));
    setPlan(null);
  }, []);

  useEffect(() => { reload().catch(() => setFailed(true)); }, [reload]);

  useEffect(() => {
    if (!playing || !data) return;
    const id = setInterval(() => setFrame(f => (f + 1) % data.plumes.length), 700);
    return () => clearInterval(id);
  }, [playing, data]);

  // Space plays and pauses; arrow keys step through the forecast.
  useEffect(() => {
    if (!data) return;
    const n = data.plumes.length;
    const onKey = (e: KeyboardEvent) => {
      if (typing(e.target)) return;
      if (e.key === ' ') { e.preventDefault(); setPlaying(p => !p); }
      else if (e.key === 'ArrowRight') { setPlaying(false); setFrame(f => (f + 1) % n); }
      else if (e.key === 'ArrowLeft') { setPlaying(false); setFrame(f => (f - 1 + n) % n); }
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [data]);

  if (!data) {
    return (
      <div className="loading">
        <div className="when">{failed ? 'No forecast yet' : 'Loading'}</div>
        {failed && <div>Start the server with <code>py -m uvicorn app:app</code>, then reload.</div>}
      </div>
    );
  }

  const city = data.cities.find(c => c.id === cityId) ?? null;
  const selectCity = (id: string) => { setCityId(id); setTab('cities'); };

  return (
    <>
      <Masthead data={data} />
      <aside>
        <Clock data={data} frame={frame} onRefreshed={reload} />
        <nav role="tablist">
          {TABS.map(t => (
            <button key={t} role="tab" aria-selected={tab === t} onClick={() => setTab(t)}>{LABEL[t]}</button>
          ))}
        </nav>
        <section className="pane" hidden={tab !== 'cities'}>
          {city
            ? <CityDetail city={city} hour={hourAt(data, frame)} onBack={() => setCityId(null)} />
            : <CitiesPane data={data} onSelect={selectCity} />}
        </section>
        <section className="pane" hidden={tab !== 'plan'}><PlanPane plan={plan} onPlan={setPlan} /></section>
        <section className="pane" hidden={tab !== 'ask'}><AskPane /></section>
        <section className="pane" hidden={tab !== 'proof'}><ProofPane /></section>
      </aside>
      <main>
        <SmokeMap data={data} frame={frame} city={city} plan={plan} onSelectCity={selectCity} />
        <div className="legend" aria-hidden="true">
          <div><span className="sw" style={{ background: 'var(--fire)' }} />Fire</div>
          <div><span className="sw" style={{ background: 'var(--ink)' }} />Smoke</div>
          <div><span className="sw wind" />Wind, dot points downwind</div>
          <div><span className="sw" style={{ background: 'transparent', borderColor: 'var(--field)', borderWidth: 3 }} />Stop this fire</div>
        </div>
        <Timeline data={data} frame={frame} playing={playing}
          onTogglePlay={() => setPlaying(p => !p)}
          onSeek={f => { setPlaying(false); setFrame(f); }} />
      </main>
    </>
  );
}
