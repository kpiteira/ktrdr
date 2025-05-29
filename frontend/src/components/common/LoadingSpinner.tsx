import React, { FC } from 'react';

interface LoadingSpinnerProps {
  size?: 'small' | 'medium' | 'large';
  color?: string;
  message?: string;
  inline?: boolean;
}

const LoadingSpinner: FC<LoadingSpinnerProps> = ({
  size = 'medium',
  color = '#1976d2',
  message,
  inline = false
}) => {
  const sizeMap = {
    small: '16px',
    medium: '24px',
    large: '32px'
  };

  const spinnerSize = sizeMap[size];

  if (inline) {
    return (
      <div style={{
        display: 'inline-flex',
        alignItems: 'center',
        gap: '0.5rem'
      }}>
        <div 
          style={{
            width: spinnerSize,
            height: spinnerSize,
            border: `2px solid ${color}20`,
            borderTop: `2px solid ${color}`,
            borderRadius: '50%',
            animation: 'spin 1s linear infinite'
          }}
        />
        {message && (
          <span style={{ 
            color: '#666', 
            fontSize: size === 'small' ? '0.8rem' : '0.9rem' 
          }}>
            {message}
          </span>
        )}
        
        {/* CSS animation */}
        <style>{`
          @keyframes spin {
            0% { transform: rotate(0deg); }
            100% { transform: rotate(360deg); }
          }
        `}</style>
      </div>
    );
  }

  return (
    <div style={{
      display: 'flex',
      flexDirection: 'column',
      alignItems: 'center',
      justifyContent: 'center',
      gap: '1rem',
      padding: '2rem',
      color: '#666'
    }}>
      <div 
        style={{
          width: spinnerSize,
          height: spinnerSize,
          border: `3px solid ${color}20`,
          borderTop: `3px solid ${color}`,
          borderRadius: '50%',
          animation: 'spin 1s linear infinite'
        }}
      />
      {message && (
        <div style={{ 
          textAlign: 'center',
          fontSize: size === 'small' ? '0.8rem' : '0.9rem'
        }}>
          {message}
        </div>
      )}
      
      {/* CSS animation */}
      <style>{`
        @keyframes spin {
          0% { transform: rotate(0deg); }
          100% { transform: rotate(360deg); }
        }
      `}</style>
    </div>
  );
};

export default LoadingSpinner;