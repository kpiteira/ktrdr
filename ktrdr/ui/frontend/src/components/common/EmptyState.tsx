import React, { FC, ReactNode } from 'react';

interface EmptyStateProps {
  icon?: string;
  title: string;
  description?: string;
  action?: ReactNode;
  compact?: boolean;
}

const EmptyState: FC<EmptyStateProps> = ({
  icon = '📈',
  title,
  description,
  action,
  compact = false
}) => {
  if (compact) {
    return (
      <div style={{
        padding: '1.5rem',
        textAlign: 'center',
        color: '#666',
        backgroundColor: '#fafafa',
        border: '1px dashed #ddd',
        borderRadius: '4px'
      }}>
        <div style={{ fontSize: '1.5rem', marginBottom: '0.5rem' }}>{icon}</div>
        <div style={{ fontSize: '0.9rem', fontWeight: '500', marginBottom: '0.25rem' }}>
          {title}
        </div>
        {description && (
          <div style={{ fontSize: '0.8rem', color: '#999' }}>
            {description}
          </div>
        )}
        {action && (
          <div style={{ marginTop: '0.75rem' }}>
            {action}
          </div>
        )}
      </div>
    );
  }

  return (
    <div style={{
      padding: '3rem 2rem',
      textAlign: 'center',
      color: '#666'
    }}>
      <div style={{ fontSize: '3rem', marginBottom: '1rem' }}>{icon}</div>
      <h3 style={{ 
        margin: '0 0 0.5rem 0', 
        color: '#333', 
        fontSize: '1.25rem',
        fontWeight: '500'
      }}>
        {title}
      </h3>
      {description && (
        <p style={{ 
          margin: '0 0 1.5rem 0', 
          fontSize: '0.9rem', 
          lineHeight: '1.4',
          color: '#666',
          maxWidth: '400px',
          marginLeft: 'auto',
          marginRight: 'auto'
        }}>
          {description}
        </p>
      )}
      {action && (
        <div>
          {action}
        </div>
      )}
    </div>
  );
};

export default EmptyState;