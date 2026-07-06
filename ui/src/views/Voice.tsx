import { ChevronDown, Radio } from 'lucide-react'
import { useState } from 'react'
import { Toggle } from '../components/primitives'

type Mode = 'idle' | 'listening' | 'thinking' | 'speaking'
const LABEL: Record<Mode, string> = { idle: 'idle · say “hey myro”', listening: 'listening…', thinking: 'thinking…', speaking: 'speaking…' }

export function Voice() {
  const [mode, setMode] = useState<Mode>('listening')
  const [handsFree, setHandsFree] = useState(true)

  return (
    <div className="view enter">
      <div className="voice-stage">
        <span className="pill-badge"><Radio size={12} /> on-device · nothing leaves your machine</span>

        <div className="orb" aria-hidden>
          {(mode === 'listening' || mode === 'speaking') && <><span className="ring" /><span className="ring r2" /></>}
          <span className="core" style={{ opacity: mode === 'idle' ? 0.6 : 1 }} />
        </div>

        <div className="wave" aria-hidden style={{ opacity: mode === 'idle' ? 0.3 : 1 }}>
          {Array.from({ length: 22 }).map((_, i) => (
            <i key={i} style={{ animationDelay: `${(i % 7) * 0.09}s`, height: 6 + ((i * 5) % 22) }} />
          ))}
        </div>

        <div className="mono" style={{ color: 'var(--ink-dim)', fontSize: 13 }}>
          {LABEL[mode]} · <span style={{ color: handsFree ? 'var(--signal)' : 'var(--ink-faint)' }}>“hey myro” {handsFree ? 'armed' : 'off'}</span>
        </div>

        <div className="card voice-transcript stack" style={{ gap: 10 }}>
          <div><span className="label" style={{ color: 'var(--ink-faint)' }}>heard</span>
            <div style={{ marginTop: 4 }}>what’s on my calendar today?</div></div>
          <div className="divider" />
          <div><span className="label teal">myro</span>
            <div style={{ marginTop: 4 }}>You’ve got the dentist at 3 with Dr. Ivanova. Mornings are clear.</div></div>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: 16, flexWrap: 'wrap', justifyContent: 'center' }}>
          <button
            className="btn teal"
            onMouseDown={() => setMode('listening')} onMouseUp={() => setMode('thinking')}
            onClick={() => setMode((m) => (m === 'listening' ? 'idle' : 'listening'))}>
            <span style={{
              width: 8, height: 8, borderRadius: 999, display: 'inline-block',
              background: mode === 'listening' ? 'var(--err)' : 'currentColor',
              boxShadow: mode === 'listening' ? '0 0 8px var(--err)' : 'none',
            }} />
            {mode === 'listening' ? 'listening…' : 'push to talk'}
          </button>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <span className="view-sub">hands-free</span>
            <Toggle on={handsFree} onChange={setHandsFree} label="Hands-free" />
          </div>
          <button className="chip-btn">voice: GIA <ChevronDown size={13} /></button>
        </div>

        <div className="mono" style={{ fontSize: 11.5, color: 'var(--ink-faint)' }}>:voice on · :listen · AGI_INTERFACE=voice</div>
      </div>
    </div>
  )
}
