import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'
import './styles/main.css'
import './index.css'
import App from './App.tsx'
import ServerWakeGate from './components/ServerWakeGate.tsx'
import { AuthProvider } from './lib/auth.tsx'

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <BrowserRouter>
      <AuthProvider>
        <ServerWakeGate>
          <App />
        </ServerWakeGate>
      </AuthProvider>
    </BrowserRouter>
  </StrictMode>,
)
