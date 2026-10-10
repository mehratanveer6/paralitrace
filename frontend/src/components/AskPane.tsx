import { useState } from 'react';
import { api } from '../lib';
import { Markdown } from './Markdown';
import type { ToolCall } from '../types';

const EXAMPLES = [
  'Which cities get the worst smoke tomorrow, and why?',
  'Write a school advisory for Ludhiana in Punjabi.',
  'Where should Punjab send 200 machines tomorrow?',
];

interface Turn { q: string; a?: string; tools?: ToolCall[]; model?: string; error?: string; recorded?: boolean }

const args = (input: Record<string, unknown>) =>
  Object.entries(input).map(([k, v]) => `${k}: ${typeof v === 'string' ? v : JSON.stringify(v)}`).join(', ');

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
      const { answer, tools, model, recorded } = await api.ask(text);
      setTurns(t => [{ q: text, a: answer, tools, model, recorded }, ...t.slice(1)]);
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
      <p className="note built">Built with the Strands Agents SDK (AWS open source), running on Amazon Bedrock where available.
        Answers come only from the forecast's own numbers.</p>

      {turns.map((t, i) => (
        <div className="turn" key={turns.length - i}>
          <p className="q">{t.q}</p>
          {t.tools && t.tools.length > 0 && (
            <div className="trace" aria-label="Tools the agent called">
              <span className="trace-label">Strands agent called</span>
              {t.tools.map((c, j) => <code key={j}>{c.name}({args(c.input)})</code>)}
            </div>
          )}
          {t.model && <p className="note model">Answered by <b>{t.model}</b></p>}
          {t.recorded && <p className="note">Recorded answer from the full app, on this same forecast.</p>}
          {t.a != null && <div className="ans"><Markdown text={t.a} /></div>}
          {t.error && <div className="err">{t.error}</div>}
          {t.a == null && !t.error && <p className="note">Reading the forecast</p>}
        </div>
      ))}
    </>
  );
}
