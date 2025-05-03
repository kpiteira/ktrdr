import React from 'react';
import config from '@/config';

interface DevModeIndicatorProps {
  position?: 'top-right' | 'top-left' | 'bottom-right' | 'bottom-left';
}

export const DevModeIndicator: React.FC<DevModeIndicatorProps> = ({ 
  position = 'bottom-right'
}) => {
  if (!config.debug) {
    return null;
  }

  const positionClasses = {
    'top-right': 'dev-mode-indicator-tr',
    'top-left': 'dev-mode-indicator-tl',
    'bottom-right': 'dev-mode-indicator-br',
    'bottom-left': 'dev-mode-indicator-bl',
  };

  return (
    <div className={`dev-mode-indicator ${positionClasses[position]}`}>
      <div className="dev-mode-indicator-content">
        <span className="dev-mode-indicator-badge">DEV</span>
        <span className="dev-mode-indicator-version">v{config.app.version}</span>
      </div>
    </div>
  );
};