import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
// JetBrains Mono bundled locally (no third-party font CDN → fully offline).
import '@fontsource/jetbrains-mono/400.css'
import '@fontsource/jetbrains-mono/500.css'
import '@fontsource/jetbrains-mono/600.css'
import './styles/tokens.css'
import './styles/global.css'
import App from './App'
import { AppProvider } from './lib/state'

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <AppProvider>
      <App />
    </AppProvider>
  </StrictMode>,
)
