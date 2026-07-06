// Domain types — the single contract the UI reads. lib/api.ts returns these from
// mock.ts today; swap the bodies for real localhost fetches later, types unchanged.

export type Gate = 'auto' | 'asks'
export type ViewId = 'chat' | 'voice' | 'memory' | 'routines' | 'connectors' | 'settings'
export type Retriever = 'vector' | 'keyword' | 'graph' | 'recency'

export interface Scope {
  id: string
  kind: 'global' | 'identity' | 'project'
  name: string
  sensitive: boolean
}

export interface Trace {
  id: string
  gate: Gate
  glyph: string
  name: string
  detail: string
}

export type ConfirmKind = 'calendar' | 'shell' | 'file' | 'email' | 'issue' | 'backup'
export interface ConfirmSpec {
  kind: ConfirmKind
  verb: string          // the action's name, kept through the flow: "Add", "Send", "Run"
  title: string         // one-line summary
  lines: DetailLine[]   // structured mono detail block
  destructive?: boolean
}
export interface DetailLine { k?: string; v: string; tone?: 'add' | 'del' | 'plain' }

export type MsgKind = 'text' | 'confirm' | 'done' | 'cancelled'
export interface Message {
  id: string
  role: 'user' | 'myro'
  kind: MsgKind
  text?: string
  traces?: Trace[]
  confirm?: ConfirmSpec
  resolved?: 'done' | 'cancelled'
  rerun?: string   // live mode: original text to re-send (allow_actions) on Confirm
}

export interface RetrievedMemory { id: string; text: string; retriever: Retriever }

export interface Fact {
  id: string
  text: string
  scope: Scope
  strength: number      // 0..1 — place on the forgetting curve
  decaying: boolean
  sourceTurn: number
  supersedes?: string
  node?: string         // graph node id this fact is about (for the graph inspector)
}

export interface GraphNode { id: string; label: string; kind: string; x: number; y: number; you?: boolean }
export interface GraphEdge { from: string; to: string; label: string; weak?: boolean }
export interface Graph { nodes: GraphNode[]; edges: GraphEdge[] }

export interface TimelineEntry { id: string; ts: string; turn: number; summary: string }

export interface Routine {
  id: string
  glyph: string
  name: string
  desc: string
  schedule: string
  enabled: boolean
  lastRun?: string
  nextRun?: string
  stopped?: boolean
  stoppedReason?: string
  preauthorized?: string   // the exact gated action pre-authorized at save time
}

export interface Connector {
  id: string
  name: string
  source: string
  reads: string
  connected: boolean
  networked: boolean
  write?: { label: string; via: string }
}

export interface Backend { id: string; name: string; detail: string; reachable: boolean; order: number }

export interface AuditRow { id: string; ts: string; gate: Gate; text: string }

export interface NotifyChannel { id: string; name: string; status: string; on: boolean }
