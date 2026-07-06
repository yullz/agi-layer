import { useApp } from '../lib/state'

export function Toasts() {
  const { toasts } = useApp()
  return (
    <div className="toast-wrap" aria-live="polite" aria-atomic="false">
      {toasts.map((t) => (
        <div key={t.id} className={`toast ${t.gate === 'asks' ? 'asks' : ''}`} role="status">
          <span className="tdot" />
          {t.text}
        </div>
      ))}
    </div>
  )
}
