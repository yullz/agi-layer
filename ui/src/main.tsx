import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
// JetBrains Mono bundled locally (no third-party font CDN → fully offline).
import '@fontsource/jetbrains-mono/400.css'
import '@fontsource/jetbrains-mono/500.css'
import '@fontsource/jetbrains-mono/600.css'
import './styles/tokens.css'
import './styles/global.css'
import App from './App'
import { initApi } from './lib/api'
import { AppProvider } from './lib/state'

// Probe the backend once (sets live vs. mock), then render. The probe fails fast
// when standalone, so this doesn't delay the offline/dev case.
initApi().finally(() => {
  createRoot(document.getElementById('root')!).render(
    <StrictMode>
      <AppProvider>
        <App />
      </AppProvider>
    </StrictMode>,
  )
})
