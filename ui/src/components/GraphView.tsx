import { useEffect, useMemo, useRef, useState } from 'react'
import type { Graph } from '../lib/types'

const W = 820
const H = 520
const reduced = () => typeof window !== 'undefined' && window.matchMedia('(prefers-reduced-motion: reduce)').matches

/**
 * The one bold surface. A teal YOU node at the centre, entity neighbours in
 * slate, typed relations on the edges, amber-dashed = weak. Gentle drift, edges
 * draw on load, click a node to select it.
 */
export function GraphView({ graph, selected, onSelect }: {
  graph: Graph
  selected: string | null
  onSelect: (id: string | null) => void
}) {
  const [t, setT] = useState(0)
  const raf = useRef(0)
  useEffect(() => {
    if (reduced()) return
    let start = 0
    const loop = (ts: number) => { if (!start) start = ts; setT((ts - start) / 1000); raf.current = requestAnimationFrame(loop) }
    raf.current = requestAnimationFrame(loop)
    return () => cancelAnimationFrame(raf.current)
  }, [])

  const pos = useMemo(() => {
    const m: Record<string, { x: number; y: number }> = {}
    graph.nodes.forEach((n, i) => {
      const amp = n.you ? 2 : 6
      m[n.id] = { x: n.x + Math.sin(t * 0.5 + i) * amp, y: n.y + Math.cos(t * 0.4 + i * 1.7) * amp }
    })
    return m
  }, [graph.nodes, t])

  const neighbors = useMemo(() => {
    if (!selected) return new Set<string>()
    const s = new Set<string>([selected])
    graph.edges.forEach((e) => { if (e.from === selected) s.add(e.to); if (e.to === selected) s.add(e.from) })
    return s
  }, [selected, graph.edges])

  return (
    <svg viewBox={`0 0 ${W} ${H}`} width="100%" height="100%" role="img" aria-label="Memory knowledge graph"
      onClick={() => onSelect(null)} style={{ display: 'block', cursor: 'default' }}>
      <defs>
        <radialGradient id="youGlow" cx="50%" cy="50%" r="50%">
          <stop offset="0%" stopColor="var(--signal)" stopOpacity="0.35" />
          <stop offset="100%" stopColor="var(--signal)" stopOpacity="0" />
        </radialGradient>
      </defs>

      {graph.edges.map((e, i) => {
        const a = pos[e.from]; const b = pos[e.to]
        if (!a || !b) return null
        const dim = selected ? (!(neighbors.has(e.from) && neighbors.has(e.to))) : false
        const mx = (a.x + b.x) / 2; const my = (a.y + b.y) / 2
        const len = Math.hypot(b.x - a.x, b.y - a.y)
        return (
          <g key={i} opacity={dim ? 0.18 : 1} style={{ transition: 'opacity .25s var(--ease)' }}>
            <line
              x1={a.x} y1={a.y} x2={b.x} y2={b.y}
              stroke={e.weak ? 'var(--amber)' : 'var(--signal-deep)'}
              strokeWidth={e.weak ? 1.2 : 1.4}
              strokeDasharray={e.weak ? '4 5' : `${len}`}
              strokeDashoffset={reduced() ? 0 : undefined}
              className={e.weak ? '' : 'edge-draw'}
              style={{ ['--len' as any]: len, animationDelay: `${i * 90}ms` }}
            />
            <text x={mx} y={my - 5} textAnchor="middle" fontSize="9.5"
              fontFamily="var(--font-mono)" fill="var(--ink-faint)" style={{ letterSpacing: '.06em', pointerEvents: 'none' }}>
              {e.label}
            </text>
          </g>
        )
      })}

      {graph.nodes.map((n) => {
        const p = pos[n.id]
        const active = selected === n.id
        const dim = selected ? !neighbors.has(n.id) : false
        const r = n.you ? 30 : 20
        return (
          <g key={n.id} transform={`translate(${p.x},${p.y})`} opacity={dim ? 0.28 : 1}
            style={{ transition: 'opacity .25s var(--ease)', cursor: 'pointer' }}
            onClick={(e) => { e.stopPropagation(); onSelect(active ? null : n.id) }}
            tabIndex={0} role="button" aria-label={`${n.label} node`}
            onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); onSelect(active ? null : n.id) } }}>
            {n.you && <circle r={54} fill="url(#youGlow)" />}
            <circle
              r={active ? r + 4 : r}
              fill={n.you ? 'var(--signal-dim)' : 'var(--slate)'}
              stroke={n.you ? 'var(--signal)' : active ? 'var(--signal)' : 'var(--line-2)'}
              strokeWidth={n.you || active ? 1.8 : 1}
              style={{ transition: 'r .2s var(--ease), stroke .2s var(--ease)', filter: active ? 'drop-shadow(0 0 8px var(--signal))' : 'none' }}
            />
            <text textAnchor="middle" dy={n.you ? 4 : r + 15} fontSize={n.you ? 12 : 11}
              fontFamily="var(--font-mono)" fontWeight={n.you ? 600 : 400}
              fill={n.you ? 'var(--signal)' : 'var(--ink)'} style={{ pointerEvents: 'none', letterSpacing: n.you ? '.08em' : 0 }}>
              {n.label}
            </text>
          </g>
        )
      })}
    </svg>
  )
}
