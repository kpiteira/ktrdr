import { FC } from 'react';
import { useToast, Toast, ToastType } from '../../../context/ToastContext';

/**
 * Toast container that renders all active toast notifications
 * 
 * Positioned fixed in the top-right corner with animations.
 * Each toast can be manually dismissed or will auto-dismiss.
 */

const ToastContainer: FC = () => {
  const { toasts, dismissToast } = useToast();

  if (toasts.length === 0) {
    return null;
  }

  return (
    <div style={{
      position: 'fixed',
      top: '80px', // Below header
      right: '20px',
      zIndex: 1000,
      display: 'flex',
      flexDirection: 'column',
      gap: '0.75rem',
      maxWidth: '400px',
      pointerEvents: 'none'
    }}>
      {toasts.map((toast) => (
        <ToastItem
          key={toast.id}
          toast={toast}
          onDismiss={() => dismissToast(toast.id)}
        />
      ))}
    </div>
  );
};

interface ToastItemProps {
  toast: Toast;
  onDismiss: () => void;
}

const ToastItem: FC<ToastItemProps> = ({ toast, onDismiss }) => {
  const getToastStyles = (type: ToastType) => {
    const baseStyles = {
      padding: '1rem',
      borderRadius: '8px',
      boxShadow: '0 4px 12px rgba(0, 0, 0, 0.15)',
      border: '1px solid',
      pointerEvents: 'auto' as const,
      animation: 'slideInRight 0.3s ease-out',
      minWidth: '300px',
      maxWidth: '400px',
      wordWrap: 'break-word' as const
    };

    switch (type) {
      case 'success':
        return {
          ...baseStyles,
          backgroundColor: '#f0f9ff',
          borderColor: '#22c55e',
          color: '#065f46'
        };
      case 'error':
        return {
          ...baseStyles,
          backgroundColor: '#fef2f2',
          borderColor: '#ef4444',
          color: '#991b1b'
        };
      case 'warning':
        return {
          ...baseStyles,
          backgroundColor: '#fffbeb',
          borderColor: '#f59e0b',
          color: '#92400e'
        };
      case 'info':
        return {
          ...baseStyles,
          backgroundColor: '#f0f9ff',
          borderColor: '#3b82f6',
          color: '#1e40af'
        };
      default:
        return baseStyles;
    }
  };

  const getIcon = (type: ToastType) => {
    switch (type) {
      case 'success':
        return '✅';
      case 'error':
        return '❌';
      case 'warning':
        return '⚠️';
      case 'info':
        return 'ℹ️';
      default:
        return '📢';
    }
  };

  return (
    <div style={getToastStyles(toast.type)}>
      <div style={{
        display: 'flex',
        alignItems: 'flex-start',
        justifyContent: 'space-between',
        gap: '0.75rem'
      }}>
        <div style={{ display: 'flex', alignItems: 'flex-start', gap: '0.5rem', flex: 1 }}>
          <span style={{ fontSize: '1.2rem', flexShrink: 0 }}>
            {getIcon(toast.type)}
          </span>
          <div style={{ flex: 1 }}>
            <div style={{ 
              fontWeight: '600', 
              fontSize: '0.9rem',
              marginBottom: toast.message ? '0.25rem' : 0
            }}>
              {toast.title}
            </div>
            {toast.message && (
              <div style={{ 
                fontSize: '0.85rem', 
                opacity: 0.8,
                lineHeight: '1.4'
              }}>
                {toast.message}
              </div>
            )}
            {toast.action && (
              <button
                onClick={toast.action.onClick}
                style={{
                  marginTop: '0.5rem',
                  padding: '0.25rem 0.5rem',
                  backgroundColor: 'transparent',
                  border: '1px solid currentColor',
                  borderRadius: '4px',
                  color: 'inherit',
                  fontSize: '0.8rem',
                  cursor: 'pointer',
                  fontWeight: '500'
                }}
              >
                {toast.action.label}
              </button>
            )}
          </div>
        </div>
        <button
          onClick={onDismiss}
          style={{
            background: 'none',
            border: 'none',
            cursor: 'pointer',
            fontSize: '1.2rem',
            color: 'inherit',
            opacity: 0.6,
            padding: '0',
            lineHeight: 1,
            flexShrink: 0
          }}
          title="Dismiss"
        >
          ×
        </button>
      </div>
    </div>
  );
};

// Add CSS animations via a style tag (since we're avoiding external CSS files)
const injectToastStyles = () => {
  if (typeof document !== 'undefined') {
    const styleId = 'toast-animations';
    if (!document.getElementById(styleId)) {
      const style = document.createElement('style');
      style.id = styleId;
      style.textContent = `
        @keyframes slideInRight {
          from {
            transform: translateX(100%);
            opacity: 0;
          }
          to {
            transform: translateX(0);
            opacity: 1;
          }
        }
        
        @keyframes fadeOut {
          from {
            opacity: 1;
            transform: translateX(0);
          }
          to {
            opacity: 0;
            transform: translateX(100%);
          }
        }
      `;
      document.head.appendChild(style);
    }
  }
};

// Inject styles when component mounts
injectToastStyles();

export default ToastContainer;