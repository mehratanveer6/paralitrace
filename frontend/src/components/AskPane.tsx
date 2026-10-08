import { useState } from 'react';
import { api } from '../lib';

const EXAMPLES = [
  'Which cities get the worst smoke tomorrow, and why?',
  'Write a school advisory for Ludhiana in Punjabi.',
  'Where should Punjab send 200 machines tomorrow?',
];

export function AskPane() {
  const [q, setQ] = useState('');
  const [busy, setBusy] = useState(false);
  const [answer, setAnswer] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const ask = async (question: string) => {
    if (!question.trim()) return;
    setBusy(true); setError(null); setAnswer(null);
    try { setAnswer((await api.ask(question.trim())).answer); }
    catch (e) { setError((e as Error).message); }
    setBusy(false);
  };

  return (
    <>
      <label htmlFor="q">Ask about the smoke</label>
      <textarea id="q" value={q} onChange={e => setQ(e.target.value)}
        placeholder="Should schools in Mohali hold outdoor assembly tomorrow?" />
      <div className="ex">
        {EXAMPLES.map(ex => <button key={ex} onClick={() => { setQ(ex); ask(ex); }}>{ex}</button>)}
      </div>
      <button className="go" onClick={() => ask(q)} disabled={busy}>Ask</button>
      {busy && <p className="note">Reading the forecast</p>}
      {answer && <div className="ans">{answer}</div>}
      {error && <div className="err">{error}</div>}
    </>
  );
}
