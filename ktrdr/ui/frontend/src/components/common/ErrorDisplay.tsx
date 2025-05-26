import React, { FC } from 'react';

interface ErrorDisplayProps {
  error: string | Error;
  title?: string;
  showDetails?: boolean;
  onRetry?: () => void;
  compact?: boolean;
  inline?: boolean;
}

const ErrorDisplay: FC<ErrorDisplayProps> = ({
  error,
  title = 'Error',
  showDetails = false,
  onRetry,
  compact = false,
  inline = false
}) => {
  const errorMessage = typeof error === 'string' ? error : error.message;
  const errorStack = typeof error === 'string' ? null : error.stack;

  if (inline) {
    return (
      <div style={{
        display: 'inline-flex',
        alignItems: 'center',
        gap: '0.5rem',
        color: '#d32f2f',
        fontSize: '0.85rem'
      }}>
        <span style={{ fontSize: '1rem' }}>⚠️</span>
        <span>{errorMessage}</span>
        {onRetry && (
          <button
            onClick={onRetry}
            style={{
              background: 'none',
              border: '1px solid #d32f2f',
              color: '#d32f2f',
              padding: '0.25rem 0.5rem',
              borderRadius: '3px',
              cursor: 'pointer',
              fontSize: '0.75rem'
            }}
          >
            Retry
          </button>
        )}
      </div>
    );
  }

  if (compact) {
    return (
      <div style={{
        padding: '0.75rem',
        backgroundColor: '#ffebee',
        border: '1px solid #ffcdd2',
        borderRadius: '4px',
        color: '#d32f2f',
        fontSize: '0.85rem',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between'
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
          <span style={{ fontSize: '1rem' }}>⚠️</span>
          <span>{errorMessage}</span>
        </div>
        {onRetry && (
          <button
            onClick={onRetry}
            style={{
              background: 'none',
              border: '1px solid #d32f2f',
              color: '#d32f2f',
              padding: '0.25rem 0.5rem',
              borderRadius: '3px',
              cursor: 'pointer',
              fontSize: '0.75rem'
            }}
          >
            Retry
          </button>
        )}
      </div>
    );
  }

  return (
    <div style={{
      padding: '2rem',
      backgroundColor: '#ffebee',
      border: '1px solid #ffcdd2',
      borderRadius: '8px',
      color: '#d32f2f',
      textAlign: 'center',
      maxWidth: '500px',
      margin: '0 auto'
    }}>
      <div style={{ fontSize: '2rem', marginBottom: '1rem' }}>⚠️</div>
      <h3 style={{ margin: '0 0 1rem 0', color: '#d32f2f' }}>{title}</h3>
      <p style={{ margin: '0 0 1rem 0', fontSize: '0.9rem', lineHeight: '1.4' }}>
        {errorMessage}
      </p>
      
      {showDetails && errorStack && (
        <details style={{ marginTop: '1rem', textAlign: 'left' }}>
          <summary style={{ cursor: 'pointer', marginBottom: '0.5rem' }}>
            Show technical details
          </summary>
          <pre style={{
            background: '#f5f5f5',
            padding: '0.75rem',
            borderRadius: '4px',
            fontSize: '0.75rem',
            overflow: 'auto',
            color: '#333',
            border: '1px solid #ddd'
          }}>
            {errorStack}
          </pre>
        </details>
      )}
      
      {onRetry && (
        <button
          onClick={onRetry}
          style={{
            marginTop: '1rem',
            padding: '0.5rem 1rem',
            backgroundColor: '#d32f2f',
            color: 'white',
            border: 'none',
            borderRadius: '4px',
            cursor: 'pointer',
            fontSize: '0.9rem'
          }}
        >
          Try Again
        </button>
      )}
    </div>
  );
};

export default ErrorDisplay;