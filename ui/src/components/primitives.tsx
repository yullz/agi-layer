import { Lock } from 'lucide-react'
import type { CSSProperties, ReactNode } from 'react'
import type { Scope } from '../lib/types'

/** teal AUTO · amber ASKS · neutral read-only — the trust boundary as a pill. */
export function Tag({ kind, children }: { kind: 'auto' | 'asks' | 'read' | 'err'; children?: ReactNode }) {
  const txt = children ?? (kind === 'auto' ? 'AUTO' : kind === 'asks' ? 'ASKS' : kind === 'read' ? 'read-only' : 'stopped')
  return <span className={`tag ${kind}`}>{txt}</span>
}

export function ReachDot({ state }: { state: 'on' | 'off' | 'warn' }) {
  return <span className={`reachdot ${state}`} aria-hidden />
}

export function Toggle({ on, onChange, label }: { on: boolean; onChange: (v: boolean) => void; label?: string }) {
  return (
    <button
      role="switch" aria-checked={on} aria-label={label}
      className={`toggle ${on ? 'on' : ''}`} onClick={() => onChange(!on)}
    >
      <span className="knob" />
    </button>
  )
}

/** The forgetting curve — teal segments fill by strength; decaying reads dim. */
export function Meter({ strength, decaying }: { strength: number; decaying?: boolean }) {
  const total = 6
  const filled = Math.max(1, Math.round(strength * total))
  return (
    <span className="meter">
      <span className="meter-track">
        {Array.from({ length: total }).map((_, i) => (
          <span key={i} className={`meter-seg ${i < filled ? (decaying ? 'dim' : 'fill') : ''}`} />
        ))}
      </span>
      <span className="meter-label">{decaying ? 'decaying' : strength > 0.75 ? 'strong' : 'held'}</span>
    </span>
  )
}

export function ScopeTag({ scope }: { scope: Scope }) {
  const label = scope.kind === 'project' ? `project:${scope.name}` : scope.name
  return (
    <span className="label" style={{ display: 'inline-flex', alignItems: 'center', gap: 5 }}>
      {label}
      {scope.sensitive && <Lock size={11} style={{ color: 'var(--amber)' }} />}
    </span>
  )
}

export function HudPanel({ children, className = '', style }: { children: ReactNode; className?: string; style?: CSSProperties }) {
  return <div className={`hud ${className}`} style={style}>{children}</div>
}
