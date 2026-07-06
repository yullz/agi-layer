import { useEffect } from 'react'
import type { ComponentType } from 'react'
import { Boot } from './components/Boot'
import { ConfirmCard } from './components/ConfirmCard'
import { Palette } from './components/Palette'
import { Shell } from './components/Shell'
import { Toasts } from './components/Toast'
import { useApp } from './lib/state'
import { Chat } from './views/Chat'
import { Connectors } from './views/Connectors'
import { Memory } from './views/Memory'
import { Routines } from './views/Routines'
import { Settings } from './views/Settings'
import { Voice } from './views/Voice'
import type { ViewId } from './lib/types'

const VIEWS: Record<ViewId, ComponentType> = {
  chat: Chat, voice: Voice, memory: Memory, routines: Routines, connectors: Connectors, settings: Settings,
}

export default function App() {
  const { view, paletteOpen, setPaletteOpen, modalConfirm, resolveModal } = useApp()
  const Active = VIEWS[view]

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'k') { e.preventDefault(); setPaletteOpen(!paletteOpen) }
      if (e.key === 'Escape') { setPaletteOpen(false); if (modalConfirm) resolveModal(false) }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [paletteOpen, setPaletteOpen, modalConfirm, resolveModal])

  return (
    <>
      <div className="grain" aria-hidden />
      <Boot />
      <Shell key={view}><Active /></Shell>
      <Palette />
      <Toasts />
      {modalConfirm && (
        <div className="palette-overlay" onClick={() => resolveModal(false)}>
          <div role="dialog" aria-modal="true" aria-label={modalConfirm.spec.title}
            style={{ width: 'min(520px, 92vw)', marginTop: '4vh' }} onClick={(e) => e.stopPropagation()}>
            <ConfirmCard
              spec={modalConfirm.spec}
              onConfirm={() => resolveModal(true)}
              onCancel={() => resolveModal(false)}
              onEdit={() => resolveModal(false)}
            />
          </div>
        </div>
      )}
    </>
  )
}
