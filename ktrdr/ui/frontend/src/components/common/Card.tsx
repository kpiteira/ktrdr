import React from 'react';

interface CardProps {
  title?: string;
  subtitle?: string;
  icon?: React.ReactNode;
  actions?: React.ReactNode;
  footer?: React.ReactNode;
  isLoading?: boolean;
  children: React.ReactNode;
  className?: string;
  style?: React.CSSProperties;
}

export const Card: React.FC<CardProps> = ({
  title,
  subtitle,
  icon,
  actions,
  footer,
  isLoading = false,
  children,
  className = '',
  style = {},
}) => {
  const cardClasses = [
    'card',
    isLoading ? 'card-loading' : '',
    className
  ].filter(Boolean).join(' ');

  // Apply less aggressive constraining styles to fix layout issues
  const cardStyle: React.CSSProperties = {
    ...style,
    maxWidth: '100%',
    boxSizing: 'border-box',
    // Less restrictive overflow to avoid hiding content
    overflowX: 'hidden',
    // Less aggressive containment that won't break tabs
    contain: 'paint'
  };

  return (
    <div className={cardClasses} style={cardStyle}>
      {(title || subtitle || actions) && (
        <div className="card-header">
          <div className="card-header-left">
            {icon && <div className="card-icon">{icon}</div>}
            <div className="card-titles">
              {title && <h3 className="card-title">{title}</h3>}
              {subtitle && <p className="card-subtitle">{subtitle}</p>}
            </div>
          </div>
          {actions && <div className="card-actions">{actions}</div>}
        </div>
      )}
      <div className="card-body" style={{ maxWidth: '100%', overflowX: 'hidden' }}>
        {isLoading ? (
          <div className="card-loading-spinner">
            <svg width="24" height="24" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
              <circle cx="12" cy="12" r="10" fill="none" stroke="currentColor" strokeWidth="4" strokeDasharray="42" strokeDashoffset="14">
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
          </div>
        ) : children}
      </div>
      {footer && <div className="card-footer">{footer}</div>}
    </div>
  );
};