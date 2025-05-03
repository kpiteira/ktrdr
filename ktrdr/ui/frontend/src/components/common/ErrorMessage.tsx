import React from 'react';

type ErrorSeverity = 'error' | 'warning' | 'info';

interface ErrorMessageProps {
  message: string;
  severity?: ErrorSeverity;
  details?: string;
  actionLabel?: string;
  onAction?: () => void;
  className?: string;
}

export const ErrorMessage: React.FC<ErrorMessageProps> = ({
  message,
  severity = 'error',
  details,
  actionLabel,
  onAction,
  className = '',
}) => {
  const errorClasses = [
    'error-message',
    `error-${severity}`,
    className
  ].filter(Boolean).join(' ');

  const renderIcon = () => {
    switch (severity) {
      case 'error':
        return (
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
            <path d="M12 2C6.48 2 2 6.48 2 12C2 17.52 6.48 22 12 22C17.52 22 22 17.52 22 12C22 6.48 17.52 2 12 2ZM13 17H11V15H13V17ZM13 13H11V7H13V13Z" fill="currentColor" />
          </svg>
        );
      case 'warning':
        return (
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
            <path d="M1 21H23L12 2L1 21ZM13 18H11V16H13V18ZM13 14H11V10H13V14Z" fill="currentColor" />
          </svg>
        );
      case 'info':
        return (
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
            <path d="M12 2C6.48 2 2 6.48 2 12C2 17.52 6.48 22 12 22C17.52 22 22 17.52 22 12C22 6.48 17.52 2 12 2ZM13 17H11V11H13V17ZM13 9H11V7H13V9Z" fill="currentColor" />
          </svg>
        );
      default:
        return null;
    }
  };

  return (
    <div 
      className={errorClasses} 
      role={severity === 'error' ? 'alert' : 'status'}
      aria-live={severity === 'error' ? 'assertive' : 'polite'}
    >
      <div className="error-icon">
        {renderIcon()}
      </div>
      <div className="error-content">
        <p className="error-text">{message}</p>
        {details && <p className="error-details">{details}</p>}
      </div>
      {actionLabel && onAction && (
        <button className="error-action" onClick={onAction}>
          {actionLabel}
        </button>
      )}
    </div>
  );
};