/**
 * ToastContainer — renders toast notifications
 */

import React from 'react';
import { useUiStore } from '../../stores/uiStore';

const icons: Record<string, string> = {
  success: '✅',
  error: '❌',
  info: 'ℹ️',
};

const ToastContainer: React.FC = () => {
  const toasts = useUiStore(state => state.toasts);

  if (toasts.length === 0) return null;

  return (
    <div id="toast-container">
      {toasts.map(toast => (
        <div key={toast.id} className="toast">
          <span>{icons[toast.type] || 'ℹ️'}</span>
          <span>{toast.message}</span>
        </div>
      ))}
    </div>
  );
};

export default ToastContainer;
