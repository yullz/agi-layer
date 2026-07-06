import { useEffect, useMemo, useState } from 'react'
import { useApp } from '../lib/state'
import type { ViewId } from '../lib/types'

interface Cmd { key: string; desc: string; run: () => void }

/** ⌘K / Ctrl-K overlay — run a :command, jump to a view, search memory. */
export function Palette() {
  const { paletteOpen, setPaletteOpen, setView, toast } = useApp()
  const [q, setQ] = useState('')
  const [sel, setSel] = useState(0)

  const go = (v: ViewId) => () => { setView(v); setPaletteOpen(false) }
  const commands: Cmd[] = useMemo(() => [
    { key: ':chat', desc: 'go to chat', run: go('chat') },
    { key: ':memory', desc: 'see what I remember', run: go('memory') },
    { key: ':routines', desc: 'scheduled tasks', run: go('routines') },
    { key: ':connectors', desc: 'your real-world sources', run: go('connectors') },
    { key: ':voice', desc: 'hands-free', run: go('voice') },
    { key: ':settings', desc: 'brain · backups · audit', run: go('settings') },
    { key: ':do <task>', desc: 'act, don’t just answer', run: () => { setView('chat'); setPaletteOpen(false) } },
    { key: ':backup', desc: 'snapshot everything now', run: () => { setPaletteOpen(false); toast('Backed up.') } },
    { key: ':starters', desc: 'install the ready-made routines', run: () => { setView('routines'); setPaletteOpen(false) } },
    { key: ':search memory', desc: 'fused recall', run: go('memory') },
    // eslint-disable-next-line react-hooks/exhaustive-deps
  ], [])

  const filtered = commands.filter((c) => (c.key + c.desc).toLowerCase().includes(q.toLowerCase()))

  useEffect(() => { setSel(0) }, [q, paletteOpen])
  useEffect(() => { if (paletteOpen) setQ('') }, [paletteOpen])

  if (!paletteOpen) return null
  return (
    <div className="palette-overlay" onClick={() => setPaletteOpen(false)}>
      <div className="palette" role="dialog" aria-label="Command palette" onClick={(e) => e.stopPropagation()}>
        <input
          className="palette-input mono" autoFocus placeholder="run a command, jump somewhere, search memory…"
          value={q} onChange={(e) => setQ(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === 'Escape') setPaletteOpen(false)
            else if (e.key === 'ArrowDown') { e.preventDefault(); setSel((s) => Math.min(s + 1, filtered.length - 1)) }
            else if (e.key === 'ArrowUp') { e.preventDefault(); setSel((s) => Math.max(s - 1, 0)) }
            else if (e.key === 'Enter') filtered[sel]?.run()
          }}
        />
        <div className="palette-list">
          {filtered.map((c, i) => (
            <button key={c.key} className={`palette-item ${i === sel ? 'sel' : ''}`}
              onMouseEnter={() => setSel(i)} onClick={c.run}>
              <span className="pk">{c.key}</span>
              <span className="pd">{c.desc}</span>
            </button>
          ))}
          {filtered.length === 0 && <div className="palette-item"><span className="pd">no match — try :memory or :do</span></div>}
        </div>
      </div>
    </div>
  )
}
