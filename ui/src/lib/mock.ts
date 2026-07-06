// Sample state — realistic, hard-coded, so the whole app is navigable offline.
// api.ts reads from here; swap those bodies for real fetches later.
import type {
  AuditRow, Backend, Connector, Fact, Graph, Message, NotifyChannel,
  RetrievedMemory, Routine, Scope, TimelineEntry,
} from './types'

export const SCOPES: Scope[] = [
  { id: 'whaletrack', kind: 'project', name: 'whaletrack', sensitive: false },
  { id: 'finance', kind: 'project', name: 'finance', sensitive: true },
  { id: 'identity', kind: 'identity', name: 'identity', sensitive: false },
  { id: 'global', kind: 'global', name: 'global', sensitive: false },
]

export const BACKENDS: Backend[] = [
  { id: 'claude', name: 'Claude', detail: 'Pro/Max · Agent SDK · signed in', reachable: true, order: 1 },
  { id: 'ollama', name: 'Ollama · Qwen', detail: 'local · qwen3:14b · reachable', reachable: true, order: 2 },
  { id: 'echo', name: 'echo', detail: 'offline fallback · always on', reachable: true, order: 3 },
]

export const INITIAL_MESSAGES: Message[] = [
  {
    id: 'm1', role: 'user', kind: 'text',
    text: 'add a calendar event for the dentist tomorrow at 3',
  },
  {
    id: 'm2', role: 'myro', kind: 'confirm',
    confirm: {
      kind: 'calendar', verb: 'Add', title: 'Add “Dentist” to your calendar',
      lines: [
        { k: 'event', v: 'Dentist' },
        { k: 'when', v: 'Tomorrow · 3:00–4:00 PM' },
        { k: 'calendar', v: 'work.ics' },
      ],
    },
  },
  {
    id: 'm3', role: 'user', kind: 'text',
    text: 'what did I decide about pricing?',
  },
  {
    id: 'm4', role: 'myro', kind: 'text',
    text: 'You settled on the $9 tier — you felt $12 read as greedy for a solo tool, and $9 still clears your costs with room to run the local model.',
    traces: [
      { id: 't1', gate: 'auto', glyph: '◈', name: 'searched memory', detail: '3 hits · reranked · read-only' },
    ],
  },
]

export const RETRIEVED: RetrievedMemory[] = [
  { id: 'r1', text: 'Dentist is Dr. Ivanova', retriever: 'graph' },
  { id: 'r2', text: 'Prefers no morning appointments', retriever: 'vector' },
  { id: 'r3', text: 'Working hours 9:00–18:00', retriever: 'recency' },
  { id: 'r4', text: 'Calendar file is work.ics', retriever: 'keyword' },
]

export const TOOLS_THIS_TURN = ['calendar', 'web', 'memory', 'files', 'git', 'notify']

export const FACTS: Fact[] = [
  {
    id: 'f1', text: 'Dentist is Dr. Ivanova', scope: SCOPES[2], node: 'ivanova',
    strength: 0.86, decaying: false, sourceTurn: 4,
  },
  {
    id: 'f2', text: 'Prefers no morning appointments', scope: SCOPES[2], node: 'dentist',
    strength: 0.34, decaying: true, sourceTurn: 4,
  },
  {
    id: 'f3', text: 'Chose the $9 pricing tier', scope: SCOPES[0], node: 'pricing',
    strength: 0.7, decaying: false, sourceTurn: 11, supersedes: '$12 tier · 2 days ago',
  },
  {
    id: 'f4', text: 'Building whaletrack — a solo analytics tool', scope: SCOPES[0], node: 'whaletrack',
    strength: 0.92, decaying: false, sourceTurn: 2,
  },
  {
    id: 'f5', text: 'Based in Sofia (Europe/Sofia)', scope: SCOPES[2], node: 'sofia',
    strength: 0.8, decaying: false, sourceTurn: 3,
  },
  {
    id: 'f6', text: 'Salary paid on the 25th', scope: SCOPES[1], node: 'you',
    strength: 0.6, decaying: false, sourceTurn: 19,
  },
]

export const GRAPH: Graph = {
  nodes: [
    { id: 'you', label: 'YOU', kind: 'person', x: 400, y: 250, you: true },
    { id: 'whaletrack', label: 'whaletrack', kind: 'project', x: 620, y: 150 },
    { id: 'ivanova', label: 'Dr. Ivanova', kind: 'person', x: 190, y: 130 },
    { id: 'dentist', label: 'dentist', kind: 'event', x: 210, y: 320 },
    { id: 'sofia', label: 'Sofia', kind: 'place', x: 430, y: 430 },
    { id: 'pricing', label: '$9 tier', kind: 'decision', x: 660, y: 340 },
    { id: 'qwen', label: 'qwen3:14b', kind: 'tool', x: 560, y: 440 },
  ],
  edges: [
    { from: 'you', to: 'whaletrack', label: 'builds' },
    { from: 'you', to: 'dentist', label: 'has appt' },
    { from: 'dentist', to: 'ivanova', label: 'with' },
    { from: 'you', to: 'sofia', label: 'lives in' },
    { from: 'whaletrack', to: 'pricing', label: 'priced at' },
    { from: 'you', to: 'qwen', label: 'runs', weak: true },
    { from: 'ivanova', to: 'sofia', label: 'near', weak: true },
  ],
}

export const TIMELINE: TimelineEntry[] = [
  { id: 'e1', ts: '14:22:07', turn: 24, summary: 'Recalled the $9 pricing decision · read-only' },
  { id: 'e2', ts: '14:21:40', turn: 23, summary: 'Asked to add a dentist event → awaiting confirm' },
  { id: 'e3', ts: '09:03:11', turn: 21, summary: 'Morning brief ran · calendar + 4 web sources' },
  { id: 'e4', ts: 'Yesterday 18:47', turn: 19, summary: 'Learned: salary paid on the 25th [finance]' },
  { id: 'e5', ts: 'Yesterday 11:12', turn: 11, summary: 'Decision: $9 tier — superseded $12' },
  { id: 'e6', ts: '2 days ago 08:00', turn: 4, summary: 'Onboarding: dentist, no mornings, Sofia' },
]

export const ROUTINES: Routine[] = [
  {
    id: 'rt1', glyph: 'sun', name: 'Morning brief', desc: 'Reads calendar, email, and web sources, then summarizes.',
    schedule: '08:00 daily', enabled: true, lastRun: 'ran 08:00 ✓', nextRun: 'tomorrow 08:00',
  },
  {
    id: 'rt2', glyph: 'moon', name: 'Nightly backup', desc: 'Snapshots data/ to your private repo, encrypted.',
    schedule: '02:00 daily', enabled: true, lastRun: 'ran 02:00 ✓', nextRun: 'tonight 02:00',
    preauthorized: 'git push → private repo (encrypted)',
  },
  {
    id: 'rt3', glyph: 'inbox', name: 'Link digest', desc: 'Collects links you saved and summarizes them at lunch.',
    schedule: '12:30 daily', enabled: false, lastRun: 'never', nextRun: 'paused',
  },
  {
    id: 'rt4', glyph: 'flag', name: 'Weekly competitor scan', desc: 'Browses three competitor sites and notes what changed.',
    schedule: 'Mon 09:00', enabled: false,
    stopped: true, stoppedReason: 'a step needed a login it wasn’t authorized for — nothing ran',
  },
]

export const CONNECTORS: Connector[] = [
  {
    id: 'git', name: 'Git repo', source: '~/dev/whaletrack', reads: 'log · status',
    connected: true, networked: false,
  },
  {
    id: 'cal', name: 'Calendar', source: 'work.ics · url', reads: 'upcoming events',
    connected: true, networked: false, write: { label: 'add event', via: 'ICS' },
  },
  {
    id: 'mail', name: 'Email', source: 'archive.mbox · IMAP', reads: 'recent messages',
    connected: true, networked: true, write: { label: 'send email', via: 'SMTP' },
  },
  {
    id: 'gh', name: 'GitHub', source: 'whaletrack repo', reads: 'issues · PRs · activity',
    connected: true, networked: true, write: { label: 'open issue', via: 'REST' },
  },
]

export const AUDIT: AuditRow[] = [
  { id: 'a1', ts: '14:22:07', gate: 'auto', text: 'search_memory("pricing") → 3 hits' },
  { id: 'a2', ts: '14:19:55', gate: 'asks', text: 'calendar_add_event("Dentist") → confirmed · ran' },
  { id: 'a3', ts: '14:18:02', gate: 'auto', text: 'web_search("dentist sofia hours") → 5 sources' },
  { id: 'a4', ts: '09:03:12', gate: 'auto', text: 'git_log(n=5) → read-only' },
  { id: 'a5', ts: '02:00:03', gate: 'asks', text: 'backup → git push (pre-authorized) · ran' },
  { id: 'a6', ts: 'Yesterday', gate: 'asks', text: 'email_send → cancelled by you · nothing sent' },
]

export const NOTIFY: NotifyChannel[] = [
  { id: 'ntfy', name: 'ntfy', status: 'topic: myro-sofia · connected', on: true },
  { id: 'telegram', name: 'Telegram', status: 'authorized chat only', on: true },
  { id: 'pushover', name: 'Pushover', status: 'not configured', on: false },
]

// Action verbs → a mock ConfirmCard is raised; otherwise a read-only answer.
export const ACTION_VERBS = [
  'send', 'add', 'schedule', 'open', 'write', 'run', 'log in', 'login',
  'buy', 'post', 'delete', 'remove', 'push', 'create', 'email', 'book', 'pay',
]
