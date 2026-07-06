// The one data seam. Every view calls this module; today it resolves from
// mock.ts with a small delay. To wire the real backend, replace each body with a
// fetch to the localhost API (e.g. http://127.0.0.1:8787) — signatures stay put.
import * as mock from './mock'
import type {
  AuditRow, Backend, Connector, ConfirmSpec, Fact, Graph, Message, NotifyChannel,
  RetrievedMemory, Routine, Scope, TimelineEntry,
} from './types'

const wait = (ms = 90) => new Promise<void>((r) => setTimeout(r, ms))
let id = 100
const uid = (p: string) => `${p}${++id}`

export const api = {
  async scopes(): Promise<Scope[]> { await wait(); return mock.SCOPES },
  async backends(): Promise<Backend[]> { await wait(); return mock.BACKENDS },

  // --- chat -------------------------------------------------------------
  async messages(): Promise<Message[]> { await wait(); return mock.INITIAL_MESSAGES },
  async retrieved(): Promise<RetrievedMemory[]> { await wait(); return mock.RETRIEVED },
  async tools(): Promise<string[]> { await wait(); return mock.TOOLS_THIS_TURN },

  /** Mock reasoning: an action verb → a ConfirmCard; otherwise a read-only answer. */
  async respond(text: string): Promise<Message> {
    await wait(320)
    const t = text.toLowerCase()
    const acts = mock.ACTION_VERBS.some((v) => t.includes(v))
    if (acts) {
      return { id: uid('m'), role: 'myro', kind: 'confirm', confirm: inferConfirm(text) }
    }
    return {
      id: uid('m'), role: 'myro', kind: 'text',
      text: readOnlyAnswer(text),
      traces: [{ id: uid('t'), gate: 'auto', glyph: '◈', name: 'searched memory', detail: '2 hits · read-only' }],
    }
  },

  // --- memory -----------------------------------------------------------
  async facts(): Promise<Fact[]> { await wait(); return mock.FACTS },
  async graph(): Promise<Graph> { await wait(); return mock.GRAPH },
  async timeline(): Promise<TimelineEntry[]> { await wait(); return mock.TIMELINE },
  async reinforce(_factId: string): Promise<void> { await wait() },
  async forget(_factId: string): Promise<void> { await wait() },

  // --- routines / connectors / settings ---------------------------------
  async routines(): Promise<Routine[]> { await wait(); return mock.ROUTINES },
  async runRoutine(_id: string): Promise<void> { await wait(260) },
  async connectors(): Promise<Connector[]> { await wait(); return mock.CONNECTORS },
  async audit(): Promise<AuditRow[]> { await wait(); return mock.AUDIT },
  async notifyChannels(): Promise<NotifyChannel[]> { await wait(); return mock.NOTIFY },

  /** Consequential action executed after the user confirms. */
  async confirmAction(_spec: ConfirmSpec): Promise<void> { await wait(200) },
}

function inferConfirm(text: string): ConfirmSpec {
  const t = text.toLowerCase()
  if (t.includes('email') || t.includes('send')) {
    return {
      kind: 'email', verb: 'Send', title: 'Send this email',
      lines: [
        { k: 'to', v: 'alex@whaletrack.dev' },
        { k: 'subject', v: 'Running a little late' },
        { k: 'body', v: 'Hey — I’ll be about 10 minutes behind. Start without me.' },
      ],
    }
  }
  if (t.includes('run') || t.includes('build') || t.includes('deploy')) {
    return {
      kind: 'shell', verb: 'Run', title: 'Run this command', destructive: true,
      lines: [{ v: '$ npm run build && ./deploy.sh --prod' }],
    }
  }
  if (t.includes('issue') || t.includes('open') || t.includes('github')) {
    return {
      kind: 'issue', verb: 'Open', title: 'Open a GitHub issue',
      lines: [
        { k: 'repo', v: 'whaletrack' },
        { k: 'title', v: 'Login button unresponsive on Safari' },
      ],
    }
  }
  if (t.includes('write') || t.includes('save')) {
    return {
      kind: 'file', verb: 'Write', title: 'Write to notes.md',
      lines: [
        { k: 'file', v: 'notes.md' },
        { v: '+ Pricing locked at $9', tone: 'add' },
        { v: '- (was $12)', tone: 'del' },
      ],
    }
  }
  return {
    kind: 'calendar', verb: 'Add', title: 'Add this to your calendar',
    lines: [
      { k: 'event', v: extractSubject(text) },
      { k: 'when', v: 'Tomorrow · 3:00–4:00 PM' },
      { k: 'calendar', v: 'work.ics' },
    ],
  }
}

function extractSubject(text: string): string {
  const cleaned = text.replace(/^(add|schedule|book|create)\s+(a|an|the)?\s*/i, '').trim()
  return cleaned.split(/\s+for\s+|\s+at\s+|\s+on\s+/i)[0].slice(0, 40) || 'New event'
}

function readOnlyAnswer(text: string): string {
  const t = text.toLowerCase()
  if (t.includes('pricing') || t.includes('price')) return 'You went with the $9 tier — it clears costs and doesn’t read as greedy for a solo tool.'
  if (t.includes('calendar') || t.includes('today') || t.includes('tomorrow')) return 'Tomorrow you’ve got the dentist at 3 with Dr. Ivanova. Mornings are clear — you like it that way.'
  if (t.includes('remember') || t.includes('know')) return 'I keep what matters and let the rest fade. Open Memory to see, correct, or forget any of it.'
  return 'Here’s what I found from memory — nothing changed, this was read-only. Tell me to `:do` something if you want me to act.'
}
