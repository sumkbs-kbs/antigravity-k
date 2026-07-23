// @ts-nocheck
import React from 'react';
import ReactDOM from 'react-dom/client';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import App from './App';
import './styles/index.css';

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
if (typeof window !== 'undefined' && (window as any).mermaid) {
  (window as any).mermaid.initialize({ startOnLoad: false, theme: 'dark' });
}

// ─── Global Error Handler ──────────────────────────────────────────
window.addEventListener('unhandledrejection', (event) => {
  console.error('[Unhandled Promise Rejection]', event.reason);
});

window.addEventListener('error', (event) => {
  if (event.target && (event.target as HTMLElement).tagName === 'SCRIPT') return;
  console.error('[Global Error]', event.error || event.message);
});

// ─── Render ────────────────────────────────────────────────────────
ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <QueryClientProvider client={queryClient}>
      <App />
    </QueryClientProvider>
  </React.StrictMode>
);
