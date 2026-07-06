import { useState } from 'react'
import type { Trace } from '../lib/types'

/** Compact mono record of a tool call. Teal dot = safe, amber = gated. */
export function TraceChip({ trace }: { trace: Trace }) {
  const [open, setOpen] = useState(false)
  return (
    <button
      className={`trace ${trace.gate === 'auto' ? 'safe' : 'gated'}`}
      onClick={() => setOpen((o) => !o)}
      style={{ animation: 'enter .3s var(--ease)' }}
      title="Show call detail"
    >
      <span className="tdot" />
      <span aria-hidden style={{ color: 'var(--ink-faint)' }}>{trace.glyph}</span>
      <span className="tname">{trace.name}</span>
      <span className="tdetail">· {open ? trace.detail : trace.detail.split(' · ')[0]}</span>
    </button>
  )
}
