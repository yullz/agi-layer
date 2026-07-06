import { createContext, useCallback, useContext, useMemo, useRef, useState } from 'react'
import type { ReactNode } from 'react'
import { SCOPES } from './mock'
import type { ConfirmSpec, Gate, Scope, ViewId } from './types'

interface Toast { id: number; text: string; gate: Gate }
interface ModalConfirm { spec: ConfirmSpec; resolve: (ok: boolean) => void }

interface AppState {
  view: ViewId
  setView: (v: ViewId) => void
  scope: Scope
  setScope: (s: Scope) => void
  scopes: Scope[]
  paletteOpen: boolean
  setPaletteOpen: (b: boolean) => void
  inspectorOpen: boolean
  setInspectorOpen: (b: boolean) => void
  toasts: Toast[]
  toast: (text: string, gate?: Gate) => void
  modalConfirm: ModalConfirm | null
  requestConfirm: (spec: ConfirmSpec) => Promise<boolean>
  resolveModal: (ok: boolean) => void
}

const Ctx = createContext<AppState | null>(null)

export function AppProvider({ children }: { children: ReactNode }) {
  const [view, setView] = useState<ViewId>('chat')
  const [scope, setScope] = useState<Scope>(SCOPES[0])
  const [paletteOpen, setPaletteOpen] = useState(false)
  const [inspectorOpen, setInspectorOpen] = useState(false)
  const [toasts, setToasts] = useState<Toast[]>([])
  const [modalConfirm, setModalConfirm] = useState<ModalConfirm | null>(null)
  const tid = useRef(0)

  const toast = useCallback((text: string, gate: Gate = 'auto') => {
    const t = { id: ++tid.current, text, gate }
    setToasts((cur) => [...cur, t])
    setTimeout(() => setToasts((cur) => cur.filter((x) => x.id !== t.id)), 2600)
  }, [])

  const requestConfirm = useCallback(
    (spec: ConfirmSpec) =>
      new Promise<boolean>((resolve) => setModalConfirm({ spec, resolve })),
    [],
  )
  const resolveModal = useCallback((ok: boolean) => {
    setModalConfirm((m) => { m?.resolve(ok); return null })
  }, [])

  const value = useMemo<AppState>(() => ({
    view, setView, scope, setScope, scopes: SCOPES,
    paletteOpen, setPaletteOpen, inspectorOpen, setInspectorOpen,
    toasts, toast, modalConfirm, requestConfirm, resolveModal,
  }), [view, scope, paletteOpen, inspectorOpen, toasts, toast, modalConfirm, requestConfirm, resolveModal])

  return <Ctx.Provider value={value}>{children}</Ctx.Provider>
}

export function useApp(): AppState {
  const v = useContext(Ctx)
  if (!v) throw new Error('useApp outside AppProvider')
  return v
}
