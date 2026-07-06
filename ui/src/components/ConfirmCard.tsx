import { Calendar, Check, CircleDot, FilePen, HardDriveDownload, Mail, Pencil, Terminal, X } from 'lucide-react'
import type { LucideIcon } from 'lucide-react'
import { Tag } from './primitives'
import type { ConfirmKind, ConfirmSpec } from '../lib/types'

const ICON: Record<ConfirmKind, LucideIcon> = {
  calendar: Calendar, shell: Terminal, file: FilePen, email: Mail, issue: CircleDot, backup: HardDriveDownload,
}

/**
 * The trust gate. Shows exactly what Myro will do; nothing runs without Confirm.
 * Confirm is amber; for destructive ops it is NOT auto-focused (Cancel is).
 */
export function ConfirmCard({
  spec, onConfirm, onCancel, onEdit,
}: {
  spec: ConfirmSpec
  onConfirm: () => void
  onCancel: () => void
  onEdit?: () => void
}) {
  // Focus Cancel for destructive ops, Confirm otherwise — never the destructive default.
  return (
    <div className="confirm" role="group" aria-label={`Confirm: ${spec.title}`}>
      <div className="confirm-head">
        {(() => { const I = ICON[spec.kind] ?? CircleDot; return <span aria-hidden style={{ color: 'var(--amber)', display: 'inline-flex' }}><I size={16} /></span> })()}
        <Tag kind="asks" />
        <span className="ttl">{spec.title}</span>
      </div>
      <div className="confirm-detail">
        {spec.lines.map((l, i) => (
          <div key={i}>
            {l.k && <span className="k">{l.k}: </span>}
            <span className={l.tone === 'add' ? 'add' : l.tone === 'del' ? 'del' : ''}>{l.v}</span>
          </div>
        ))}
      </div>
      <div className="confirm-actions">
        <button autoFocus={!spec.destructive} className="btn amber" onClick={onConfirm}>
          <Check size={15} /> Confirm
        </button>
        <button className="btn" onClick={onEdit}><Pencil size={14} /> Edit</button>
        <button autoFocus={spec.destructive} className="btn ghost" onClick={onCancel}>
          <X size={14} /> Cancel
        </button>
      </div>
    </div>
  )
}
