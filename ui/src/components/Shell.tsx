import {
  Bell, ChevronDown, Cpu, HardDriveDownload, Lock, MessageSquare, Mic,
  Network, Plug, Settings as SettingsIcon,
} from 'lucide-react'
import { useEffect, useState } from 'react'
import type { ReactNode } from 'react'
import { useApp } from '../lib/state'
import { BACKENDS } from '../lib/mock'
import { ReachDot } from './primitives'
import type { ViewId } from '../lib/types'

const NAV: { id: ViewId; icon: ReactNode; label: string }[] = [
  { id: 'chat', icon: <MessageSquare size={19} />, label: 'Chat' },
  { id: 'voice', icon: <Mic size={19} />, label: 'Voice' },
  { id: 'memory', icon: <Network size={19} />, label: 'Memory' },
  { id: 'routines', icon: <Cpu size={19} />, label: 'Routines' },
  { id: 'connectors', icon: <Plug size={19} />, label: 'Connectors' },
  { id: 'settings', icon: <SettingsIcon size={19} />, label: 'Settings' },
]

function ScopeMenu() {
  const { scope, setScope, scopes } = useApp()
  const [open, setOpen] = useState(false)
  useEffect(() => {
    if (!open) return
    const close = () => setOpen(false)
    window.addEventListener('click', close)
    return () => window.removeEventListener('click', close)
  }, [open])
  return (
    <div style={{ position: 'relative' }}>
      <button className="scope-sel" onClick={(e) => { e.stopPropagation(); setOpen((o) => !o) }} aria-haspopup="listbox" aria-expanded={open}>
        <span className="label" style={{ color: 'var(--ink-faint)' }}>scope</span>
        <span className="mono" style={{ fontSize: 13, color: 'var(--ink)' }}>{scope.name}</span>
        {scope.sensitive && <Lock size={12} className="lock" />}
        <ChevronDown size={14} style={{ color: 'var(--ink-faint)' }} />
      </button>
      {open && (
        <div role="listbox" style={{
          position: 'absolute', top: 40, left: 0, minWidth: 210, zIndex: 70,
          background: 'var(--carbon)', border: '1px solid var(--line-2)', borderRadius: 12,
          padding: 6, boxShadow: '0 24px 60px -20px rgba(0,0,0,.8)',
        }}>
          {scopes.map((s) => (
            <button key={s.id} className="palette-item" onClick={() => { setScope(s); setOpen(false) }}>
              <span className="pk mono" style={{ fontSize: 13 }}>{s.kind === 'project' ? `project:${s.name}` : s.name}</span>
              {s.sensitive && <span className="pd" style={{ display: 'flex', alignItems: 'center', gap: 4 }}><Lock size={11} style={{ color: 'var(--amber)' }} /> local-only</span>}
            </button>
          ))}
        </div>
      )}
    </div>
  )
}

export function Shell({ children }: { children: ReactNode }) {
  const { view, setView, setPaletteOpen } = useApp()
  const brain = BACKENDS.find((b) => b.reachable)!
  return (
    <div className="app">
      <header className="topbar">
        <div className="brand display">MYRO<span className="cursor" /></div>
        <ScopeMenu />
        <div className="topbar-spacer" />
        <button className="brain-ind" onClick={() => setView('settings')} title="Active brain — open model settings">
          <ReachDot state="on" />
          <span className="mono" style={{ fontSize: 13 }}>{brain.name.split(' ')[0]}</span>
          <span className="label hide-narrow" style={{ color: 'var(--ink-faint)' }}>reachable</span>
        </button>
        <div className="chip-btn hide-narrow" title="Runs on your machine">
          <HardDriveDownload size={14} /> <span className="mono" style={{ fontSize: 12 }}>offline-ok</span>
        </div>
        <button className="chip-btn" aria-label="Notifications"><Bell size={16} /></button>
      </header>

      <div className="body">
        <nav className="rail" aria-label="Primary">
          {NAV.map((n) => (
            <button key={n.id} className={`rail-item ${view === n.id ? 'active' : ''}`}
              onClick={() => setView(n.id)} aria-current={view === n.id ? 'page' : undefined} aria-label={n.label}>
              {n.icon}
              <span className="rail-tip">{n.label}</span>
            </button>
          ))}
          <div className="rail-spacer" />
          <button className="rail-kbd" onClick={() => setPaletteOpen(true)} title="Command palette (⌘K)">⌘K</button>
        </nav>
        <main className="stage">{children}</main>
      </div>
    </div>
  )
}
