import { Lock, Pencil, RefreshCw, Search, Trash2 } from 'lucide-react'
import { useEffect, useMemo, useState } from 'react'
import type { KeyboardEvent as ReactKeyboardEvent } from 'react'
import { api } from '../lib/api'
import { useApp } from '../lib/state'
import { GraphView } from '../components/GraphView'
import { Meter, ScopeTag } from '../components/primitives'
import type { Fact, Graph, TimelineEntry } from '../lib/types'

type Tab = 'facts' | 'graph' | 'timeline'

export function Memory() {
  const { toast } = useApp()
  const [tab, setTab] = useState<Tab>('facts')
  const [q, setQ] = useState('')
  const [facts, setFacts] = useState<Fact[]>([])
  const [graph, setGraph] = useState<Graph>({ nodes: [], edges: [] })
  const [timeline, setTimeline] = useState<TimelineEntry[]>([])
  const [sel, setSel] = useState<string | null>(null)
  const [editing, setEditing] = useState<string | null>(null)
  const [editDraft, setEditDraft] = useState('')

  useEffect(() => {
    api.facts().then(setFacts)
    api.graph().then(setGraph)
    api.timeline().then(setTimeline)
  }, [])

  const shownFacts = facts.filter((f) => f.text.toLowerCase().includes(q.toLowerCase()))
  const shownTimeline = timeline.filter((e) =>
    `${e.summary} ${e.ts} turn ${e.turn}`.toLowerCase().includes(q.toLowerCase()))

  function reinforce(id: string) {
    setFacts((fs) => fs.map((x) => (x.id === id ? { ...x, strength: Math.min(1, x.strength + 0.18), decaying: false } : x)))
    api.reinforce(id); toast('Reinforced.')
  }
  function forget(id: string) {
    setFacts((fs) => fs.filter((x) => x.id !== id)); api.forget(id); toast('Forgotten.')
  }
  function saveEdit(id: string) {
    const text = editDraft.trim()
    if (text) setFacts((fs) => fs.map((x) => (x.id === id ? { ...x, text } : x)))
    setEditing(null); if (text) toast('Updated.')
  }
  const TABS: Tab[] = ['facts', 'graph', 'timeline']
  function onTabKey(e: ReactKeyboardEvent, t: Tab) {
    const i = TABS.indexOf(t)
    if (e.key === 'ArrowRight') { e.preventDefault(); setTab(TABS[(i + 1) % 3]) }
    if (e.key === 'ArrowLeft') { e.preventDefault(); setTab(TABS[(i + 2) % 3]) }
  }
  const selNode = graph.nodes.find((n) => n.id === sel)
  const selNeighbors = useMemo(() => {
    if (!sel) return []
    return graph.edges
      .filter((e) => e.from === sel || e.to === sel)
      .map((e) => ({ label: e.from === sel ? e.to : e.from, rel: e.label, weak: e.weak }))
  }, [sel, graph.edges])

  return (
    <div className="view enter viewsplit" role="region" aria-label="Memory">
      <div className="mainpane">
        <div className="view-scroll">
          <div className="view-pad">
            <div className="view-head"><h1 className="view-title">Memory</h1></div>

            <div className="searchbar hud">
              <Search size={17} style={{ color: 'var(--ink-dim)' }} />
              <input value={q} onChange={(e) => setQ(e.target.value)}
                placeholder="search everything I remember — meaning, keywords, connections, recency" aria-label="Search memory" />
              <span className="label" style={{ color: 'var(--ink-faint)' }}>fused · reranked</span>
            </div>
            <div className="mono" style={{ fontSize: 11.5, color: 'var(--ink-faint)', marginTop: 8 }}>
              global &amp; identity facts always available, whatever scope you’re in
            </div>

            <div className="tabs" role="tablist" aria-label="Memory views">
              {TABS.map((t) => (
                <button key={t} role="tab" id={`tab-${t}`} aria-controls={`panel-${t}`} aria-selected={tab === t}
                  tabIndex={tab === t ? 0 : -1} className={`tab ${tab === t ? 'on' : ''}`}
                  onClick={() => setTab(t)} onKeyDown={(e) => onTabKey(e, t)}>
                  {t[0].toUpperCase() + t.slice(1)}
                </button>
              ))}
            </div>

            {tab === 'facts' && (
              <div className="stack" role="tabpanel" id="panel-facts" aria-labelledby="tab-facts">
                {shownFacts.map((f) => (
                  <div key={f.id} className="fact">
                    <span className="fmark">◈</span>
                    <div style={{ flex: 1, minWidth: 0 }}>
                      {editing === f.id ? (
                        <input className="fact-edit mono" value={editDraft} autoFocus aria-label="Edit fact"
                          onChange={(e) => setEditDraft(e.target.value)} onBlur={() => saveEdit(f.id)}
                          onKeyDown={(e) => { if (e.key === 'Enter') saveEdit(f.id); if (e.key === 'Escape') setEditing(null) }} />
                      ) : (
                        <div className="ftext">{f.text}</div>
                      )}
                      {f.supersedes && <div className="fsuper"><RefreshCw size={12} /> supersedes “{f.supersedes}”</div>}
                      <div className="fact-meta">
                        <ScopeTag scope={f.scope} />
                        {f.scope.sensitive && <span className="label" style={{ display: 'inline-flex', gap: 4, color: 'var(--amber)' }}><Lock size={11} /> local-only</span>}
                        <Meter strength={f.strength} decaying={f.decaying} />
                        <span className="mono" style={{ fontSize: 11, color: 'var(--ink-faint)' }}>from turn #{f.sourceTurn}</span>
                        <div className="fact-actions">
                          <button className="btn ghost sm" onClick={() => reinforce(f.id)}>reinforce</button>
                          <button className="btn ghost sm" onClick={() => { setEditing(f.id); setEditDraft(f.text) }}><Pencil size={12} /> edit</button>
                          <button className="btn ghost sm" onClick={() => forget(f.id)}><Trash2 size={12} /> forget</button>
                        </div>
                      </div>
                    </div>
                  </div>
                ))}
                {shownFacts.length === 0 && (
                  <div className="empty">
                    <div className="display">Nothing remembered yet.</div>
                    As we talk I’ll keep what matters and let the rest fade — you can always see, correct, or forget any of it here.
                  </div>
                )}
              </div>
            )}

            {tab === 'graph' && (
              <div className="graph-wrap hud" role="tabpanel" id="panel-graph" aria-labelledby="tab-graph">
                <GraphView graph={graph} selected={sel} onSelect={setSel} />
                <div className="graph-legend">
                  <span>click a node → its facts &amp; relations</span>
                  <span style={{ color: 'var(--amber)' }}>— — amber = weak / uncertain edge</span>
                </div>
              </div>
            )}

            {tab === 'timeline' && (
              <div role="tabpanel" id="panel-timeline" aria-labelledby="tab-timeline">
                {shownTimeline.map((e) => (
                  <div key={e.id} className="tl-row">
                    <span className="tl-ts">{e.ts}</span>
                    <div>
                      <div className="tl-sum">{e.summary}</div>
                      <span className="mono" style={{ fontSize: 11, color: 'var(--ink-faint)' }}>turn #{e.turn}</span>
                    </div>
                  </div>
                ))}
                {shownTimeline.length === 0 && <div className="empty">Nothing in the timeline matches “{q}”.</div>}
              </div>
            )}
          </div>
        </div>
      </div>

      <aside className="inspector" aria-label="Detail">
        {tab === 'graph' && selNode ? (
          <>
            <div className="insp-group">
              <div className="label teal">node</div>
              <div className="display" style={{ fontSize: 18 }}>{selNode.label}</div>
              <span className="label" style={{ color: 'var(--ink-faint)' }}>{selNode.kind}</span>
            </div>
            <div className="insp-group">
              <div className="label teal">related facts</div>
              {facts.filter((f) => f.node === selNode.id).map((f) => (
                <div key={f.id} className="insp-card"><div className="txt">◈ {f.text}</div></div>
              ))}
              {facts.filter((f) => f.node === selNode.id).length === 0 && (
                <div className="insp-card"><div className="txt" style={{ color: 'var(--ink-dim)' }}>No stored facts about this node yet.</div></div>
              )}
            </div>
            <div className="insp-group">
              <div className="label teal">relations</div>
              {selNeighbors.map((n, i) => (
                <div key={i} className="insp-row">
                  <span className="k mono" style={{ fontSize: 12 }}>{n.rel}</span>
                  <span className="v" style={{ color: n.weak ? 'var(--amber)' : 'var(--ink)' }}>{graph.nodes.find((x) => x.id === n.label)?.label}{n.weak ? ' · weak' : ''}</span>
                </div>
              ))}
            </div>
          </>
        ) : (
          <div className="insp-group">
            <div className="label teal">detail</div>
            <div className="insp-card"><div className="txt" style={{ color: 'var(--ink-dim)' }}>
              {tab === 'graph' ? 'Click a node in the graph to see its facts and typed relations.' : 'Everything here is yours — reinforce what matters, forget what doesn’t. Nothing leaves your machine.'}
            </div></div>
          </div>
        )}
      </aside>
    </div>
  )
}
