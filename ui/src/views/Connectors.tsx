import { Calendar, GitBranch, Github, Mail, ShieldCheck } from 'lucide-react'
import { useEffect, useState } from 'react'
import type { ReactNode } from 'react'
import { api } from '../lib/api'
import { useApp } from '../lib/state'
import { ReachDot, Tag } from '../components/primitives'
import type { Connector, ConfirmSpec } from '../lib/types'

const ICON: Record<string, ReactNode> = {
  git: <GitBranch size={18} />, cal: <Calendar size={18} />, mail: <Mail size={18} />, gh: <Github size={18} />,
}

function writeSpec(c: Connector): ConfirmSpec {
  if (c.id === 'cal') return { kind: 'calendar', verb: 'Add', title: 'Add an event', lines: [{ k: 'event', v: 'New event' }, { k: 'when', v: 'Tomorrow 3:00 PM' }, { k: 'calendar', v: c.source }] }
  if (c.id === 'mail') return { kind: 'email', verb: 'Send', title: 'Send an email', lines: [{ k: 'to', v: 'alex@whaletrack.dev' }, { k: 'subject', v: '(draft)' }, { k: 'via', v: 'SMTP' }] }
  return { kind: 'issue', verb: 'Open', title: 'Open a GitHub issue', lines: [{ k: 'repo', v: 'whaletrack' }, { k: 'title', v: '(draft)' }] }
}

export function Connectors() {
  const { requestConfirm, toast } = useApp()
  const [connectors, setConnectors] = useState<Connector[]>([])
  useEffect(() => { api.connectors().then(setConnectors) }, [])

  async function doWrite(c: Connector) {
    const spec = writeSpec(c)
    const ok = await requestConfirm(spec)
    if (ok) { await api.confirmAction(spec); toast(c.id === 'mail' ? 'Sent.' : c.id === 'cal' ? 'Added.' : 'Opened.', 'asks') }
  }

  return (
    <div className="view enter">
      <div className="view-scroll">
        <div className="view-pad" style={{ maxWidth: 880 }}>
          <div className="view-head"><h1 className="view-title">Connectors</h1></div>
          <div className="view-sub" style={{ marginBottom: 16 }}>Your real world — read locally, on your machine.</div>

          <div className="note" style={{ marginBottom: 18 }}>
            <ShieldCheck size={16} style={{ color: 'var(--signal)', flex: 'none', marginTop: 1 }} />
            <div>Every read is <b>read-only</b> and runs on its own. The only things that <b>ask first</b> are the write
              actions below — sending, adding, opening. Networked sources (GitHub, email) are config-gated.</div>
          </div>

          <div className="grid-cards">
            {connectors.map((c) => (
              <div key={c.id} className="card stack" style={{ gap: 12 }}>
                <div className="conn-head">
                  <span className="conn-icon">{ICON[c.id]}</span>
                  <div>
                    <div className="card-title">{c.name}</div>
                    <div className="mono" style={{ fontSize: 12, color: 'var(--ink-dim)' }}>{c.source}</div>
                  </div>
                  <div style={{ marginLeft: 'auto', display: 'flex', alignItems: 'center', gap: 7 }}>
                    <ReachDot state="on" />
                    <span className="label" style={{ color: 'var(--ink-faint)' }}>{c.networked ? 'config-gated' : 'connected'}</span>
                  </div>
                </div>
                <div className="row-between">
                  <span className="mono" style={{ fontSize: 12, color: 'var(--ink-dim)' }}>reads: {c.reads}</span>
                  <Tag kind="read" />
                </div>
                {c.write && (
                  <div className="row-between" style={{ borderTop: '1px solid var(--line)', paddingTop: 12 }}>
                    <span style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                      <Tag kind="asks" /> <span style={{ fontSize: 13 }}>{c.write.label} · {c.write.via}</span>
                    </span>
                    <button className="btn sm" onClick={() => doWrite(c)}>{c.write.label} →</button>
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
