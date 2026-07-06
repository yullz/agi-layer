import { Mic, Send } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'
import { api } from '../lib/api'
import { BACKENDS } from '../lib/mock'
import { useApp } from '../lib/state'
import { ConfirmCard } from '../components/ConfirmCard'
import { TraceChip } from '../components/TraceChip'
import { Tag } from '../components/primitives'
import type { Message, RetrievedMemory } from '../lib/types'

const reduced = () => window.matchMedia('(prefers-reduced-motion: reduce)').matches

// An action keeps its name through the flow: Add → Added, Send → Sent, …
const PAST: Record<string, string> = { Add: 'Added', Send: 'Sent', Run: 'Ran', Write: 'Wrote', Open: 'Opened' }
const pastOf = (verb: string) => PAST[verb] ?? 'Done'

function StreamText({ text }: { text: string }) {
  const [n, setN] = useState(reduced() ? text.length : 0)
  useEffect(() => {
    if (reduced()) { setN(text.length); return }
    setN(0)
    let i = 0
    const id = setInterval(() => { i += 2; setN(i); if (i >= text.length) clearInterval(id) }, 14)
    return () => clearInterval(id)
  }, [text])
  return <span>{text.slice(0, n)}{n < text.length && <span className="cur" />}</span>
}

export function Chat() {
  const { scope, toast, setView } = useApp()
  const [messages, setMessages] = useState<Message[]>([])
  const [retrieved, setRetrieved] = useState<RetrievedMemory[]>([])
  const [tools, setTools] = useState<string[]>([])
  const [draft, setDraft] = useState('')
  const [busy, setBusy] = useState(false)
  const scrollRef = useRef<HTMLDivElement>(null)
  const taRef = useRef<HTMLTextAreaElement>(null)

  useEffect(() => {
    api.messages().then(setMessages)
    api.retrieved().then(setRetrieved)
    api.tools().then(setTools)
  }, [])
  useEffect(() => {
    const el = scrollRef.current
    if (el) el.scrollTop = el.scrollHeight
  }, [messages, busy])

  const grow = () => {
    const ta = taRef.current
    if (ta) { ta.style.height = 'auto'; ta.style.height = Math.min(ta.scrollHeight, 150) + 'px' }
  }

  async function send() {
    const text = draft.trim()
    if (!text || busy) return
    setDraft(''); requestAnimationFrame(grow)
    setMessages((m) => [...m, { id: 'u' + Date.now(), role: 'user', kind: 'text', text }])
    setBusy(true)
    const reply = await api.respond(text)
    setBusy(false)
    setMessages((m) => [...m, reply])
  }

  async function resolve(msg: Message, outcome: 'done' | 'cancelled') {
    setMessages((m) => m.map((x) => (x.id === msg.id ? { ...x, kind: outcome, resolved: outcome } : x)))
    if (outcome === 'cancelled') return
    toast(`${pastOf(msg.confirm!.verb)}.`, 'asks')
    if (msg.rerun) {                       // live: actually run it now (allow_actions)
      setBusy(true)
      const res = await api.confirmChat(msg.rerun)
      setBusy(false)
      if (res) setMessages((m) => [...m, res])
    }
  }

  const empty = messages.length === 0

  return (
    <div className="view enter viewsplit" role="region" aria-label="Chat">
      <div className="mainpane">
        <div className="chat-scroll" ref={scrollRef}>
          <div className="chat-inner">
            <div className="session-line">
              <span className="label">session</span>
              <span className="mono" style={{ fontSize: 12, color: 'var(--ink-dim)' }}>project: {scope.name}</span>
            </div>

            {empty && (
              <div className="empty">
                <div className="display">I’m listening.</div>
                Ask a question, or tell me to do something — <span className="kbd">:do</span> if you want me to act.
              </div>
            )}

            {messages.map((m) => {
              if (m.role === 'user') return <div key={m.id} className="msg-user"><div className="bubble">{m.text}</div></div>
              return (
                <div key={m.id} className="msg-myro">
                  {m.kind === 'confirm' && m.confirm && (
                    <ConfirmCard
                      spec={m.confirm}
                      onConfirm={() => resolve(m, 'done')}
                      onCancel={() => resolve(m, 'cancelled')}
                      onEdit={() => taRef.current?.focus()}
                    />
                  )}
                  {m.kind === 'done' && m.confirm && (
                    <div className="donechip">✓ {pastOf(m.confirm.verb)} — logged to audit</div>
                  )}
                  {m.kind === 'cancelled' && <div className="cancelchip">Cancelled — nothing done</div>}
                  {m.kind === 'text' && m.text && <div className="myro-prose"><StreamText text={m.text} /></div>}
                  {m.traces && m.traces.length > 0 && (
                    <div className="msg-traces">{m.traces.map((t) => <TraceChip key={t.id} trace={t} />)}</div>
                  )}
                </div>
              )
            })}
            {busy && <div className="msg-myro"><div className="myro-prose" style={{ color: 'var(--ink-dim)' }}>thinking<span className="cur" /></div></div>}
          </div>
        </div>

        <div className="composer">
          <div className="composer-inner">
            <div className="composer-box">
              <button className="icon-btn" title="Talk instead" onClick={() => setView('voice')} aria-label="Voice"><Mic size={19} /></button>
              <textarea
                ref={taRef} value={draft} rows={1} aria-label="Message Myro"
                placeholder="ask me anything — or tell me to do something"
                onChange={(e) => { setDraft(e.target.value); grow() }}
                onKeyDown={(e) => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); send() } }}
              />
              <button className="icon-btn send" onClick={send} disabled={!draft.trim() || busy} aria-label="Send"><Send size={17} /></button>
            </div>
          </div>
          <div className="hintrow">
            <span className="mono"><span className="kbd">↵</span> send · <span className="kbd">:</span> commands · <span className="kbd">:do &lt;task&gt;</span> — act, don’t just answer</span>
          </div>
        </div>
      </div>

      <aside className="inspector" aria-label="Context">
        <div className="insp-group">
          <div className="label teal">retrieved memory</div>
          {retrieved.map((r) => (
            <div key={r.id} className="insp-card">
              <div className="txt">◈ {r.text}</div>
              <span className="label" style={{ color: 'var(--ink-faint)' }}>{r.retriever}</span>
            </div>
          ))}
        </div>
        <div className="insp-group">
          <div className="label teal">tools available</div>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
            {tools.map((t) => <span key={t} className="kbd">{t}</span>)}
          </div>
        </div>
        <div className="insp-group">
          <div className="label teal">this turn</div>
          <div className="insp-row"><span className="k">backend</span><span className="v">{BACKENDS[0].name.split(' ')[0]}</span></div>
          <div className="insp-row"><span className="k">scope</span><span className="v">{scope.name}</span></div>
          <div className="insp-row"><span className="k">sensitive</span><span className="v" style={{ color: scope.sensitive ? 'var(--amber)' : 'var(--ink)' }}>{scope.sensitive ? 'yes · on-box' : 'no'}</span></div>
          <div className="insp-row"><span className="k">token budget</span><span className="v">6.0k</span></div>
        </div>
        <div className="insp-group">
          <div className="label">fallback order</div>
          <div className="mono" style={{ fontSize: 12, color: 'var(--ink-dim)' }}>Claude → Ollama → echo</div>
          <div className="row-between" style={{ gap: 6, marginTop: 2 }}>
            <Tag kind="auto">safe · runs itself</Tag>
            <Tag kind="asks">asks first</Tag>
          </div>
        </div>
      </aside>
    </div>
  )
}
