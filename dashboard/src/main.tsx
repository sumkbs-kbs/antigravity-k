import React from 'react';
import ReactDOM from 'react-dom/client';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import App from './App';
import './styles/index.css';

class DashboardBootstrapError extends Error {
  constructor(message: string) {
    super(message);
    this.name = 'DashboardBootstrapError';
  }
}

function isMermaidRuntime(value: unknown): value is Readonly<{
  initialize: (options: Readonly<{ startOnLoad: boolean; theme: string }>) => void;
}> {
  return typeof value === 'object'
    && value !== null
    && 'initialize' in value
    && typeof value.initialize === 'function';
}

const enableReactDevTools = import.meta.env.DEV
  && import.meta.env.VITE_ENABLE_REACT_DEVTOOLS === '1'
  && import.meta.env.VITE_DISABLE_REACT_DEVTOOLS !== '1';

if (enableReactDevTools) {
  void import('react-grab');
  void import('react-scan');
}

// ─── React Query Client ────────────────────────────────────────────
const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: 2,
      staleTime: 10_000,
      refetchOnWindowFocus: false,
    },
  },
});

// ─── Mermaid Init ───────────────────────────────────────────────────
const mermaidRuntime: unknown = window.mermaid;
if (isMermaidRuntime(mermaidRuntime)) {
  mermaidRuntime.initialize({ startOnLoad: false, theme: 'dark' });
}

// ─── Global Error Handler ──────────────────────────────────────────
window.addEventListener('unhandledrejection', (event) => {
  console.error('[Unhandled Promise Rejection]', event.reason);
});

window.addEventListener('error', (event) => {
  if (event.target instanceof HTMLScriptElement) return;
  console.error('[Global Error]', event.error || event.message);
});

// ─── Render ────────────────────────────────────────────────────────
const rootElement = document.getElementById('root');
if (rootElement === null) throw new DashboardBootstrapError('Dashboard root element is missing.');

ReactDOM.createRoot(rootElement).render(
  <React.StrictMode>
    <QueryClientProvider client={queryClient}>
      <App />
    </QueryClientProvider>
  </React.StrictMode>
);
