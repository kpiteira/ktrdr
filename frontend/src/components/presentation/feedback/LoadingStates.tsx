import { FC, ReactNode } from 'react';

/**
 * Improved loading state components with better visual feedback
 * 
 * Provides different loading states for various UI scenarios:
 * - Spinner: General purpose loading indicator
 * - Skeleton: Content placeholders while loading
 * - ChartLoading: Specific loading state for charts
 * - ButtonLoading: Loading state for buttons
 */

interface LoadingSpinnerProps {
  size?: 'small' | 'medium' | 'large';
  color?: string;
  message?: string;
}

export const LoadingSpinner: FC<LoadingSpinnerProps> = ({ 
  size = 'medium', 
  color = '#1976d2',
  message 
}) => {
  const sizeMap = {
    small: '16px',
    medium: '24px',
    large: '32px'
  };

  const spinnerSize = sizeMap[size];

  return (
    <div style={{
      display: 'flex',
      flexDirection: 'column',
      alignItems: 'center',
      justifyContent: 'center',
      gap: '0.75rem',
      padding: '1rem'
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
          fontSize: '0.9rem',
          color: '#666',
          textAlign: 'center',
          fontWeight: '500'
        }}>
          {message}
        </div>
      )}
    </div>
  );
};

interface ChartLoadingProps {
  width: number;
  height: number;
  message?: string;
}

export const ChartLoading: FC<ChartLoadingProps> = ({ width, height, message = 'Loading chart data...' }) => {
  return (
    <div style={{
      width,
      height,
      backgroundColor: '#f8f9fa',
      border: '1px solid #e0e0e0',
      borderRadius: '8px',
      display: 'flex',
      flexDirection: 'column',
      alignItems: 'center',
      justifyContent: 'center',
      gap: '1rem',
      position: 'relative',
      overflow: 'hidden'
    }}>
      {/* Animated background pattern */}
      <div style={{
        position: 'absolute',
        top: 0,
        left: 0,
        right: 0,
        bottom: 0,
        background: 'linear-gradient(90deg, transparent, rgba(255,255,255,0.4), transparent)',
        animation: 'shimmer 2s infinite'
      }} />
      
      <div style={{
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        gap: '1rem',
        zIndex: 1
      }}>
        <div style={{ fontSize: '2rem' }}>📈</div>
        <LoadingSpinner message={message} />
      </div>
    </div>
  );
};

interface SkeletonProps {
  width?: string | number;
  height?: string | number;
  borderRadius?: string;
  count?: number;
}

export const Skeleton: FC<SkeletonProps> = ({ 
  width = '100%', 
  height = '1rem', 
  borderRadius = '4px',
  count = 1 
}) => {
  const skeletons = Array.from({ length: count }, (_, index) => (
    <div
      key={index}
      style={{
        width,
        height,
        backgroundColor: '#e0e0e0',
        borderRadius,
        animation: 'pulse 2s infinite',
        marginBottom: count > 1 && index < count - 1 ? '0.5rem' : 0
      }}
    />
  ));

  return count === 1 ? skeletons[0] : <div>{skeletons}</div>;
};

interface SidebarLoadingProps {
  isCollapsed: boolean;
}

export const SidebarLoading: FC<SidebarLoadingProps> = ({ isCollapsed }) => {
  if (isCollapsed) {
    return (
      <div style={{
        width: '40px',
        height: '100%',
        backgroundColor: '#f8f9fa',
        display: 'flex',
        justifyContent: 'center',
        alignItems: 'center',
        padding: '1rem 0'
      }}>
        <LoadingSpinner size="small" />
      </div>
    );
  }

  return (
    <div style={{
      width: '280px',
      height: '100%',
      backgroundColor: '#f8f9fa',
      padding: '1rem',
      display: 'flex',
      flexDirection: 'column',
      gap: '1rem'
    }}>
      <Skeleton height="1.5rem" width="70%" />
      <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
        <Skeleton height="2.5rem" />
        <Skeleton height="2.5rem" />
        <Skeleton height="2.5rem" />
      </div>
      <Skeleton height="3rem" />
    </div>
  );
};

interface ButtonLoadingProps {
  children: ReactNode;
  isLoading: boolean;
  disabled?: boolean;
  onClick?: () => void;
  style?: React.CSSProperties;
  loadingText?: string;
}

export const ButtonLoading: FC<ButtonLoadingProps> = ({
  children,
  isLoading,
  disabled = false,
  onClick,
  style = {},
  loadingText = 'Loading...'
}) => {
  return (
    <button
      onClick={onClick}
      disabled={disabled || isLoading}
      style={{
        position: 'relative',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        gap: '0.5rem',
        opacity: disabled || isLoading ? 0.6 : 1,
        cursor: disabled || isLoading ? 'not-allowed' : 'pointer',
        ...style
      }}
    >
      {isLoading && (
        <LoadingSpinner size="small" color="currentColor" />
      )}
      <span style={{ visibility: isLoading ? 'hidden' : 'visible' }}>
        {children}
      </span>
      {isLoading && (
        <span style={{
          position: 'absolute',
          left: '50%',
          transform: 'translateX(-50%)',
          fontSize: 'inherit'
        }}>
          {loadingText}
        </span>
      )}
    </button>
  );
};

// Inject loading animation styles
const injectLoadingStyles = () => {
  if (typeof document !== 'undefined') {
    const styleId = 'loading-animations';
    if (!document.getElementById(styleId)) {
      const style = document.createElement('style');
      style.id = styleId;
      style.textContent = `
        @keyframes spin {
          0% { transform: rotate(0deg); }
          100% { transform: rotate(360deg); }
        }
        
        @keyframes pulse {
          0%, 100% {
            opacity: 1;
          }
          50% {
            opacity: 0.5;
          }
        }
        
        @keyframes shimmer {
          0% {
            transform: translateX(-100%);
          }
          100% {
            transform: translateX(100%);
          }
        }
      `;
      document.head.appendChild(style);
    }
  }
};

injectLoadingStyles();