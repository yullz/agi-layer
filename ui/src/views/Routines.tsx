import { Play, Plus, ShieldAlert } from 'lucide-react'
import { useEffect, useState } from 'react'
import { api } from '../lib/api'
import { useApp } from '../lib/state'
import { Tag, Toggle } from '../components/primitives'
import type { Routine } from '../lib/types'

export function Routines() {
  const { toast } = useApp()
  const [routines, setRoutines] = useState<Routine[]>([])
  useEffect(() => { api.routines().then(setRoutines) }, [])

  const toggle = (id: string, on: boolean) =>
    setRoutines((rs) => rs.map((r) => (r.id === id ? { ...r, enabled: on } : r)))

  return (
    <div className="view enter">
      <div className="view-scroll">
        <div className="view-pad" style={{ maxWidth: 880 }}>
          <div className="view-head" style={{ justifyContent: 'space-between' }}>
            <h1 className="view-title">Routines</h1>
            <div style={{ display: 'flex', gap: 9 }}>
              <button className="btn ghost" onClick={() => toast('Starters installed.')}>:starters</button>
              <button className="btn teal" onClick={() => toast('New routine — draft saved.')}><Plus size={15} /> New</button>
            </div>
          </div>
          <div className="view-sub" style={{ marginBottom: 18 }}>Saved tasks I run on my own — on a schedule or on demand.</div>

          <div className="note amber" style={{ marginBottom: 18 }}>
            <ShieldAlert size={16} style={{ color: 'var(--amber)', flex: 'none', marginTop: 1 }} />
            <div>Routines run unattended, so I can’t stop to ask mid-run. If a task needs a gated action, you
              pre-authorize <b>that exact action</b> when you save it — otherwise it stays read-only and fails closed.</div>
          </div>

          <div className="stack">
            {routines.map((r) => (
              <div key={r.id} className={`card rt ${r.stopped ? 'stopped' : ''}`}>
                <div className="rt-head">
                  <span className="rt-glyph" aria-hidden>{r.glyph}</span>
                  <span className="rt-name">{r.name}</span>
                  <span className="rt-sched">{r.schedule}</span>
                  <div style={{ marginLeft: 'auto', display: 'flex', alignItems: 'center', gap: 10 }}>
                    {r.stopped ? <Tag kind="err">stopped</Tag> : <Toggle on={r.enabled} onChange={(v) => toggle(r.id, v)} label={`Enable ${r.name}`} />}
                  </div>
                </div>
                <div style={{ color: 'var(--ink-dim)', fontSize: 13.5 }}>{r.desc}</div>
                {r.preauthorized && (
                  <div className="mono" style={{ fontSize: 11.5, color: 'var(--amber)' }}>pre-authorized: {r.preauthorized}</div>
                )}
                {r.stopped ? (
                  <div className="rt-status" style={{ color: 'var(--err)' }}>◼ stopped — {r.stoppedReason}</div>
                ) : (
                  <div className="rt-status">
                    <span>● last: {r.lastRun}</span>
                    <span>next: {r.nextRun}</span>
                    <div style={{ marginLeft: 'auto', display: 'flex', gap: 6 }}>
                      <button className="btn ghost sm" onClick={() => toast('Ran.')}><Play size={12} /> Run now</button>
                      <button className="btn ghost sm">Edit</button>
                    </div>
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  )
}
