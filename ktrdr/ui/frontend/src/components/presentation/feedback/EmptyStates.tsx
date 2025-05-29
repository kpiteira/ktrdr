import { FC, ReactNode } from 'react';

/**
 * Enhanced empty state components for better user guidance
 * 
 * Provides contextual empty states that guide users on what to do next
 * instead of leaving them with blank screens.
 */

interface EmptyStateProps {
  icon?: string;
  title: string;
  description?: string;
  action?: {
    label: string;
    onClick: () => void;
  };
  children?: ReactNode;
}

export const EmptyState: FC<EmptyStateProps> = ({
  icon = '📭',
  title,
  description,
  action,
  children
}) => {
  return (
    <div style={{
      display: 'flex',
      flexDirection: 'column',
      alignItems: 'center',
      justifyContent: 'center',
      padding: '3rem 2rem',
      textAlign: 'center',
      color: '#666',
      minHeight: '300px'
    }}>
      <div style={{ 
        fontSize: '3rem', 
        marginBottom: '1rem',
        opacity: 0.7
      }}>
        {icon}
      </div>
      
      <h3 style={{
        margin: '0 0 0.5rem 0',
        fontSize: '1.25rem',
        fontWeight: '600',
        color: '#333'
      }}>
        {title}
      </h3>
      
      {description && (
        <p style={{
          margin: '0 0 1.5rem 0',
          fontSize: '0.95rem',
          lineHeight: '1.5',
          maxWidth: '400px',
          color: '#666'
        }}>
          {description}
        </p>
      )}
      
      {action && (
        <button
          onClick={action.onClick}
          style={{
            padding: '0.75rem 1.5rem',
            backgroundColor: '#1976d2',
            color: 'white',
            border: 'none',
            borderRadius: '6px',
            fontSize: '0.9rem',
            fontWeight: '500',
            cursor: 'pointer',
            transition: 'background-color 0.2s ease'
          }}
          onMouseEnter={(e) => {
            e.currentTarget.style.backgroundColor = '#1565c0';
          }}
          onMouseLeave={(e) => {
            e.currentTarget.style.backgroundColor = '#1976d2';
          }}
        >
          {action.label}
        </button>
      )}
      
      {children}
    </div>
  );
};

export const NoIndicatorsEmpty: FC<{ onAddIndicator?: () => void }> = ({ onAddIndicator }) => {
  return (
    <EmptyState
      icon="📈"
      title="No Indicators Added"
      description="Add technical indicators to start analyzing your market data. Try starting with a Simple Moving Average (SMA) or Relative Strength Index (RSI)."
      action={onAddIndicator ? {
        label: "Add Your First Indicator",
        onClick: onAddIndicator
      } : undefined}
    >
      <div style={{ 
        marginTop: '1rem', 
        fontSize: '0.85rem', 
        color: '#999',
        display: 'flex',
        flexDirection: 'column',
        gap: '0.25rem'
      }}>
        <div>💡 <strong>Tip:</strong> Use the sidebar to add indicators</div>
        <div>🎯 <strong>Overlay indicators</strong> appear on the price chart</div>
        <div>📊 <strong>Oscillators</strong> get their own panel below</div>
      </div>
    </EmptyState>
  );
};

export const NoDataEmpty: FC<{ symbol?: string; onRetry?: () => void }> = ({ symbol, onRetry }) => {
  return (
    <EmptyState
      icon="📊"
      title="No Data Available"
      description={symbol 
        ? `No market data found for ${symbol}. This might be a data connectivity issue or the symbol might not be available.`
        : "No market data found. Please check your connection and try again."
      }
      action={onRetry ? {
        label: "Retry Loading",
        onClick: onRetry
      } : undefined}
    >
      <div style={{ 
        marginTop: '1rem', 
        fontSize: '0.85rem', 
        color: '#999',
        display: 'flex',
        flexDirection: 'column',
        gap: '0.25rem'
      }}>
        <div>🔍 Try selecting a different symbol</div>
        <div>🔄 Check your internet connection</div>
        <div>⏰ Data might still be loading</div>
      </div>
    </EmptyState>
  );
};

export const SearchEmpty: FC<{ query: string; onClear?: () => void }> = ({ query, onClear }) => {
  return (
    <EmptyState
      icon="🔍"
      title="No Results Found"
      description={`No results found for "${query}". Try adjusting your search terms or browse available options.`}
      action={onClear ? {
        label: "Clear Search",
        onClick: onClear
      } : undefined}
    />
  );
};

export const ErrorState: FC<{ 
  error: string; 
  onRetry?: () => void;
  technical?: boolean;
}> = ({ error, onRetry, technical = false }) => {
  // Convert technical errors to user-friendly messages
  const getUserFriendlyError = (error: string) => {
    if (error.includes('Network Error') || error.includes('fetch')) {
      return "Connection problem. Please check your internet and try again.";
    }
    if (error.includes('404') || error.includes('Not Found')) {
      return "The requested data could not be found.";
    }
    if (error.includes('500') || error.includes('Internal Server Error')) {
      return "Server issue. Please try again in a moment.";
    }
    if (error.includes('timeout') || error.includes('Timeout')) {
      return "Request timed out. Please try again.";
    }
    if (error.includes('unauthorized') || error.includes('401')) {
      return "Access denied. Please check your credentials.";
    }
    
    // If it's a technical error and we want user-friendly, provide generic message
    if (!technical && (error.includes('Error:') || error.includes('Exception'))) {
      return "Something went wrong. Please try again.";
    }
    
    return error;
  };

  const displayError = getUserFriendlyError(error);

  return (
    <EmptyState
      icon="⚠️"
      title="Something Went Wrong"
      description={displayError}
      action={onRetry ? {
        label: "Try Again",
        onClick: onRetry
      } : undefined}
    >
      {technical && (
        <details style={{ 
          marginTop: '1rem', 
          fontSize: '0.8rem', 
          color: '#999',
          textAlign: 'left',
          maxWidth: '400px'
        }}>
          <summary style={{ cursor: 'pointer', marginBottom: '0.5rem' }}>
            Technical Details
          </summary>
          <pre style={{ 
            background: '#f5f5f5', 
            padding: '0.5rem', 
            borderRadius: '4px',
            overflow: 'auto',
            fontSize: '0.75rem'
          }}>
            {error}
          </pre>
        </details>
      )}
    </EmptyState>
  );
};

export const MaintenanceState: FC = () => {
  return (
    <EmptyState
      icon="🔧"
      title="Maintenance Mode"
      description="We're performing some updates to improve your experience. Please check back in a few minutes."
    >
      <div style={{ 
        marginTop: '1rem', 
        fontSize: '0.85rem', 
        color: '#999'
      }}>
        This usually takes just a few minutes
      </div>
    </EmptyState>
  );
};