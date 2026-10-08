import { useState } from 'react';
import { api } from '../lib';
import { Markdown } from './Markdown';

const EXAMPLES = [
  'Which cities get the worst smoke tomorrow, and why?',
  'Write a school advisory for Ludhiana in Punjabi.',
  'Where should Punjab send 200 machines tomorrow?',
];

interface Turn { q: string; a?: string; error?: string }

export function AskPane() {
  const [q, setQ] = useState('');
  const [busy, setBusy] = useState(false);
  const [turns, setTurns] = useState<Turn[]>([]);

  const ask = async (question: string) => {
    const text = question.trim();
    if (!text || busy) return;
    setBusy(true); setQ('');
    setTurns(t => [{ q: text }, ...t]);
    try {
      const { answer } = await api.ask(text);
      setTurns(t => [{ q: text, a: answer }, ...t.slice(1)]);
    } catch (e) {
      setTurns(t => [{ q: text, error: (e as Error).message }, ...t.slice(1)]);
    }
    setBusy(false);
  };

  return (
    <>
      <label htmlFor="q">Ask about the smoke</label>
      <textarea id="q" value={q} onChange={e => setQ(e.target.value)}
        onKeyDown={e => { if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) ask(q); }}
        placeholder="Should schools in Mohali hold outdoor assembly tomorrow?" />
      <div className="ex">
        {EXAMPLES.map(ex => <button key={ex} onClick={() => ask(ex)} disabled={busy}>{ex}</button>)}
      </div>
      <button className="go" onClick={() => ask(q)} disabled={busy || !q.trim()}>Ask</button>
      <span className="note hint">Ctrl + Enter also asks</span>

      {turns.map((t, i) => (
        <div className="turn" key={turns.length - i}>
          <p className="q">{t.q}</p>
          {t.a != null && <div className="ans"><Markdown text={t.a} /></div>}
          {t.error && <div className="err">{t.error}</div>}
          {t.a == null && !t.error && <p className="note">Reading the forecast</p>}
        </div>
      ))}
    </>
  );
}
