/**
 * TrainSettingsSidebar - Right sidebar for Train mode with settings and configuration
 * 
 * This placeholder sidebar will eventually contain:
 * - Backtest configuration (instead of modal)
 * - Strategy parameters
 * - Model training settings
 * - Historical performance metrics
 */

import React from 'react';
import './TrainSettingsSidebar.css';

interface TrainSettingsSidebarProps {
  isCollapsed: boolean;
  onToggleCollapse: () => void;
}

export const TrainSettingsSidebar: React.FC<TrainSettingsSidebarProps> = ({
  isCollapsed,
  onToggleCollapse
}) => {
  return (
    <div className={`train-settings-sidebar ${isCollapsed ? 'collapsed' : ''}`}>
      <div className="sidebar-header">
        <h3>Train Settings</h3>
        <button 
          onClick={onToggleCollapse}
          className="collapse-btn"
          title={isCollapsed ? "Expand settings" : "Collapse settings"}
        >
          {isCollapsed ? '◀' : '▶'}
        </button>
      </div>
      
      {!isCollapsed && (
        <div className="sidebar-content">
          <div className="coming-soon">
            <h4>🚧 Coming Soon</h4>
            <p>This sidebar will contain:</p>
            <ul>
              <li>Backtest configuration</li>
              <li>Strategy parameters</li>
              <li>Model training settings</li>
              <li>Performance metrics</li>
            </ul>
            <p className="note">
              For now, use the configuration modal when running backtests.
            </p>
          </div>
        </div>
      )}
    </div>
  );
};