import React from 'react';

type SpinnerSize = 'small' | 'medium' | 'large';

interface LoadingSpinnerProps {
  size?: SpinnerSize;
  message?: string;
  fullPage?: boolean;
  className?: string;
}

export const LoadingSpinner: React.FC<LoadingSpinnerProps> = ({
  size = 'medium',
  message,
  fullPage = false,
  className = '',
}) => {
  const sizeMap = {
    small: { width: 16, height: 16 },
    medium: { width: 32, height: 32 },
    large: { width: 48, height: 48 },
  };

  const { width, height } = sizeMap[size];

  const spinnerClasses = [
    'loading-spinner',
    `spinner-${size}`,
    fullPage ? 'spinner-fullpage' : '',
    className
  ].filter(Boolean).join(' ');

  return (
    <div className={spinnerClasses} role="status">
      <svg 
        width={width} 
        height={height} 
        viewBox="0 0 24 24" 
        xmlns="http://www.w3.org/2000/svg"
      >
        <circle 
          cx="12" 
          cy="12" 
          r="10" 
          fill="none" 
          stroke="currentColor" 
          strokeWidth="4" 
          strokeDasharray="42" 
          strokeDashoffset="14"
        >
          <animateTransform 
            attributeName="transform" 
            type="rotate" 
            from="0 12 12" 
            to="360 12 12" 
            dur="1s" 
            repeatCount="indefinite" 
          />
        </circle>
      </svg>
      {message && <p className="spinner-message">{message}</p>}
      <span className="sr-only">Loading...</span>
    </div>
  );
};