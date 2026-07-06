import { Lock, RefreshCw, Search, Trash2 } from 'lucide-react'
import { useEffect, useMemo, useState } from 'react'
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

  useEffect(() => {
    api.facts().then(setFacts)
    api.graph().then(setGraph)
    api.timeline().then(setTimeline)
  }, [])

  const shownFacts = facts.filter((f) => f.text.toLowerCase().includes(q.toLowerCase()))
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

            <div className="tabs" role="tablist">
              {(['facts', 'graph', 'timeline'] as Tab[]).map((t) => (
                <button key={t} role="tab" aria-selected={tab === t} className={`tab ${tab === t ? 'on' : ''}`} onClick={() => setTab(t)}>
                  {t[0].toUpperCase() + t.slice(1)}
                </button>
              ))}
            </div>

            {tab === 'facts' && (
              <div className="stack">
                {shownFacts.map((f) => (
                  <div key={f.id} className="fact">
                    <span className="fmark">◈</span>
                    <div style={{ flex: 1, minWidth: 0 }}>
                      <div className="ftext">{f.text}</div>
                      {f.supersedes && <div className="fsuper"><RefreshCw size={12} /> supersedes “{f.supersedes}”</div>}
                      <div className="fact-meta">
                        <ScopeTag scope={f.scope} />
                        {f.scope.sensitive && <span className="label" style={{ display: 'inline-flex', gap: 4, color: 'var(--amber)' }}><Lock size={11} /> local-only</span>}
                        <Meter strength={f.strength} decaying={f.decaying} />
                        <span className="mono" style={{ fontSize: 11, color: 'var(--ink-faint)' }}>from turn #{f.sourceTurn}</span>
                        <div className="fact-actions">
                          <button className="btn ghost sm" onClick={() => toast('Reinforced.')}>reinforce</button>
                          <button className="btn ghost sm" onClick={() => toast('Forgotten.')}><Trash2 size={12} /> forget</button>
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
              <div className="graph-wrap hud">
                <GraphView graph={graph} selected={sel} onSelect={setSel} />
                <div className="graph-legend">
                  <span>click a node → its facts &amp; relations</span>
                  <span style={{ color: 'var(--amber)' }}>— — amber = weak / uncertain edge</span>
                </div>
              </div>
            )}

            {tab === 'timeline' && (
              <div>
                {timeline.map((e) => (
                  <div key={e.id} className="tl-row">
                    <span className="tl-ts">{e.ts}</span>
                    <div>
                      <div className="tl-sum">{e.summary}</div>
                      <span className="mono" style={{ fontSize: 11, color: 'var(--ink-faint)' }}>turn #{e.turn}</span>
                    </div>
                  </div>
                ))}
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
              {facts.filter((f) => f.text.toLowerCase().includes(selNode.label.toLowerCase().split(' ')[0])).map((f) => (
                <div key={f.id} className="insp-card"><div className="txt">◈ {f.text}</div></div>
              ))}
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
