import { History, Lock, Save } from 'lucide-react'
import { useEffect, useState } from 'react'
import type { ReactNode } from 'react'
import { api } from '../lib/api'
import { BACKENDS } from '../lib/mock'
import { useApp } from '../lib/state'
import { ReachDot, Tag, Toggle } from '../components/primitives'
import type { AuditRow, NotifyChannel } from '../lib/types'

function Panel({ title, sub, children }: { title: string; sub?: string; children: ReactNode }) {
  return (
    <section className="card stack" style={{ gap: 14 }}>
      <div>
        <h2 className="card-title" style={{ fontSize: 15 }}>{title}</h2>
        {sub && <div className="view-sub">{sub}</div>}
      </div>
      {children}
    </section>
  )
}

export function Settings() {
  const { toast } = useApp()
  const [audit, setAudit] = useState<AuditRow[]>([])
  const [notify, setNotify] = useState<NotifyChannel[]>([])
  const [nightly, setNightly] = useState(true)
  const [encrypt, setEncrypt] = useState(true)
  const [mcp, setMcp] = useState(true)
  useEffect(() => { api.audit().then(setAudit); api.notifyChannels().then(setNotify) }, [])

  return (
    <div className="view enter">
      <div className="view-scroll">
        <div className="view-pad set-group" style={{ margin: '0 auto' }}>
          <div className="view-head"><h1 className="view-title">Settings</h1></div>
          <div className="stack" style={{ marginTop: 8 }}>

            <Panel title="Brain" sub="I pick the first brain I can reach, and degrade gracefully if one drops mid-turn.">
              {BACKENDS.map((b) => (
                <div key={b.id} className="backend-row">
                  <span className="order-badge">{b.order}</span>
                  <ReachDot state="on" />
                  <div style={{ flex: 1 }}>
                    <div style={{ fontWeight: 500 }}>{b.name}</div>
                    <div className="mono" style={{ fontSize: 12, color: 'var(--ink-dim)' }}>{b.detail}</div>
                  </div>
                  <span className="label" style={{ color: 'var(--signal)' }}>reachable</span>
                </div>
              ))}
              <div className="note">
                <Lock size={15} style={{ color: 'var(--signal)', flex: 'none', marginTop: 1 }} />
                <div><b>Scope-aware routing.</b> Sensitive scopes are pinned to the local model — sensitive memory is
                  never packed into a cloud-bound prompt. Extraction, summarizing, and skill-authoring all run on-box.</div>
              </div>
            </Panel>

            <Panel title="Backups" sub="Your data/ is separate from the code and gitignored — updates never touch your memories.">
              <div className="row-between"><span>Nightly backup</span><Toggle on={nightly} onChange={setNightly} label="Nightly backup" /></div>
              <div className="row-between"><span>Destination</span><span className="kbd">private GitHub repo ▾</span></div>
              <div className="row-between"><span>Encrypt before it leaves the machine</span><Toggle on={encrypt} onChange={setEncrypt} label="Encrypt" /></div>
              <button className="btn teal" style={{ alignSelf: 'flex-start' }} onClick={() => toast('Backed up.')}><Save size={14} /> Back up now</button>
            </Panel>

            <Panel title="Notifications to your phone" sub="So a scheduled briefing lands in your pocket.">
              {notify.map((n) => (
                <div key={n.id} className="row-between" style={{ borderBottom: '1px solid var(--line)', paddingBottom: 10 }}>
                  <div><div style={{ fontWeight: 500 }}>{n.name}</div><div className="mono" style={{ fontSize: 12, color: 'var(--ink-dim)' }}>{n.status}</div></div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                    <ReachDot state={n.on ? 'on' : 'off'} />
                    <button className="btn ghost sm" onClick={() => toast('Sent.', 'auto')}>Send test</button>
                  </div>
                </div>
              ))}
            </Panel>

            <Panel title="Interfaces & bridge">
              <div className="stack" style={{ gap: 8 }}>
                {[
                  ['Myro.bat · AGI_INTERFACE=api', 'this app'],
                  ['AGI_INTERFACE=voice', 'hands-free “Hey Myro”'],
                  ['AGI_INTERFACE=telegram', 'authorized chat · gated writes denied over the wire'],
                ].map(([k, v]) => (
                  <div key={k} className="row-between">
                    <span className="mono" style={{ fontSize: 12.5 }}>{k}</span>
                    <span className="view-sub">{v}</span>
                  </div>
                ))}
                <div className="divider" />
                <div className="row-between">
                  <div><div style={{ fontWeight: 500 }}>MCP bridge</div><div className="mono" style={{ fontSize: 12, color: 'var(--ink-dim)' }}>exposes ask · retrieve_memory · remember</div></div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                    <span className="kbd">http://127.0.0.1:8787</span>
                    <Toggle on={mcp} onChange={setMcp} label="MCP bridge" />
                  </div>
                </div>
              </div>
            </Panel>

            <Panel title="Governance & audit">
              <div>
                {audit.map((a) => (
                  <div key={a.id} className="audit-row">
                    <span className="ats">{a.ts}</span>
                    <Tag kind={a.gate === 'auto' ? 'auto' : 'asks'} />
                    <span className="atx">{a.text}</span>
                  </div>
                ))}
              </div>
              <div className="row-between">
                <div style={{ display: 'flex', gap: 8 }}>
                  <button className="btn ghost sm" onClick={() => toast('Snapshot saved.')}><Save size={12} /> Snapshot</button>
                  <button className="btn ghost sm" onClick={() => toast('Rolled back.')}><History size={12} /> Roll back</button>
                </div>
                <span className="mono" style={{ fontSize: 11.5, color: 'var(--ink-faint)' }}>feedback → routing optimizer · GEPA-ready · fail-closed</span>
              </div>
            </Panel>

          </div>
        </div>
      </div>
    </div>
  )
}
