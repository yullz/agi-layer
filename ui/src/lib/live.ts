// Live backend client. Talks to Myro's localhost HTTP API (interfaces/api.py).
// api.ts calls these when the backend is reachable and falls back to mock.ts
// otherwise, so the deck still runs fully standalone/offline.
//
// Same-origin by default ('/api') — the backend serves this build, so no CORS.
// Override with VITE_API_BASE for a separate dev origin.
import { SCOPES } from './mock'
import type {
  Connector, ConfirmKind, Fact, Message, Routine, Trace,
} from './types'

const BASE = (import.meta as any).env?.VITE_API_BASE ?? '/api'
let sid = 'deck'

async function get<T>(path: string): Promise<T> {
  const r = await fetch(`${BASE}${path}`, { headers: { accept: 'application/json' } })
  if (!r.ok) throw new Error(`${path} → ${r.status}`)
  return r.json() as Promise<T>
}
async function post<T>(path: string, body: unknown): Promise<T> {
  const r = await fetch(`${BASE}${path}`, {
    method: 'POST', headers: { 'content-type': 'application/json' }, body: JSON.stringify(body),
  })
  if (!r.ok) throw new Error(`${path} → ${r.status}`)
  return r.json() as Promise<T>
}

/** True if the backend answers — probed once at boot by api.ts. */
export async function reachable(): Promise<boolean> {
  try { await get('/status'); return true } catch { return false }
}

// --- shape helpers ----------------------------------------------------------
const glyphFor = (tool: string) => (/mem|recall|remember/.test(tool) ? '◈'
  : /web|search|browse|fetch/.test(tool) ? '⌕'
  : /write|file|calendar|email|issue|backup/.test(tool) ? '✎' : '›')

function tracesOf(steps: any[]): Trace[] {
  return (steps || []).map((s, i) => ({
    id: `t${i}`,
    gate: s.denied ? 'asks' : 'auto',
    glyph: glyphFor(String(s.tool || '')),
    name: String(s.tool || 'tool').replace(/_/g, ' '),
    detail: `${s.args ? s.args + ' · ' : ''}${s.result || (s.denied ? 'held — needs confirm' : 'done')}`,
  }))
}

const kindFor = (tool: string): ConfirmKind =>
  /calendar/.test(tool) ? 'calendar' : /email|smtp/.test(tool) ? 'email'
    : /issue|github/.test(tool) ? 'issue' : /shell|run/.test(tool) ? 'shell'
      : /backup/.test(tool) ? 'backup' : 'file'

let uid = 0
const mid = () => `L${Date.now()}_${uid++}`

export const live = {
  async messages(): Promise<Message[]> { return [] },   // real session starts fresh

  /** Read-only first: gated actions come back as a ConfirmCard to re-run. */
  async respond(text: string): Promise<Message> {
    const res = await post<any>('/chat', { text, sid, allow_actions: false })
    const denied = (res.steps || []).find((s: any) => s.denied)
    if (denied) {
      return {
        id: mid(), role: 'myro', kind: 'confirm', rerun: text,
        confirm: {
          kind: kindFor(String(denied.tool || '')), verb: 'Confirm',
          title: `Myro wants to ${String(denied.tool || 'act').replace(/_/g, ' ')}`,
          lines: [{ k: 'action', v: String(denied.tool || '') }, { v: String(denied.args || '') }],
        },
      }
    }
    return { id: mid(), role: 'myro', kind: 'text', text: res.reply || '', traces: tracesOf(res.steps) }
  },

  /** The confirmed re-run — now allowed to act. */
  async confirmChat(text: string): Promise<Message> {
    const res = await post<any>('/chat', { text, sid, allow_actions: true })
    return { id: mid(), role: 'myro', kind: 'text', text: res.reply || '', traces: tracesOf(res.steps) }
  },

  async facts(): Promise<Fact[]> {
    const res = await get<{ items: string[] }>(`/memory?q=&sid=${sid}`)
    return (res.items || []).map((text, i) => ({
      id: `mf${i}`, text, scope: SCOPES[3], strength: 0.72, decaying: false, sourceTurn: 0,
    }))
  },

  async routines(): Promise<Routine[]> {
    const res = await get<{ routines: any[] }>('/routines')
    return (res.routines || []).map((r, i) => ({
      id: `lr${i}`, glyph: 'sun', name: r.name, desc: r.task || 'Saved task.',
      schedule: r.schedule || 'on demand', enabled: true,
      lastRun: r.last || 'not yet', nextRun: r.schedule ? 'scheduled' : 'on demand',
    }))
  },

  async connectors(): Promise<Connector[]> {
    const res = await get<{ status: Record<string, string> }>('/connectors')
    const st = res.status || {}
    const rows: [string, string, string, boolean, { label: string; via: string } | undefined][] = [
      ['git', 'Git repo', 'log · status', false, undefined],
      ['calendar', 'Calendar', 'upcoming events', false, { label: 'add event', via: 'ICS' }],
      ['email', 'Email', 'recent messages', true, { label: 'send email', via: 'SMTP' }],
      ['github', 'GitHub', 'issues · PRs', true, { label: 'open issue', via: 'REST' }],
    ]
    return rows.map(([id, name, reads, networked, write]) => ({
      id, name, source: (st[id] || 'not configured').replace(/^ok \(|\)$/g, ''),
      reads, connected: (st[id] || '').startsWith('ok'), networked, write,
    }))
  },

  async runRoutine(name: string): Promise<void> { await post('/routines/run', { name }) },
  async forget(text: string): Promise<void> { await post('/forget', { text }) },
  async backup(): Promise<void> { await post('/backup', {}) },
}
