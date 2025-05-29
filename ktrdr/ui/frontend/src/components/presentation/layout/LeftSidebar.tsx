import { FC } from 'react';

/**
 * Left sidebar for mode selection and navigation
 * 
 * This component provides mode selection between Research, Train, and Run phases.
 * For MVP, only Research mode is functional.
 */

interface LeftSidebarProps {
  currentMode: 'research' | 'train' | 'run';
  isCollapsed: boolean;
  selectedTimeframe: string;
  onModeChange: (mode: 'research' | 'train' | 'run') => void;
  onTimeframeChange: (timeframe: string) => void;
  onToggleCollapse: () => void;
}

const LeftSidebar: FC<LeftSidebarProps> = ({
  currentMode,
  isCollapsed,
  selectedTimeframe,
  onModeChange,
  onTimeframeChange,
  onToggleCollapse
}) => {
  const modes = [
    { 
      id: 'research' as const, 
      label: 'Research', 
      icon: '🔍', 
      description: 'Analyze data and indicators',
      available: true
    },
    { 
      id: 'train' as const, 
      label: 'Train', 
      icon: '🧠', 
      description: 'Train neural networks',
      available: false
    },
    { 
      id: 'run' as const, 
      label: 'Run', 
      icon: '⚡', 
      description: 'Execute trading strategies',
      available: false
    }
  ];

  const timeframes = [
    { id: '1m', label: '1 Minute' },
    { id: '5m', label: '5 Minutes' },
    { id: '15m', label: '15 Minutes' },
    { id: '30m', label: '30 Minutes' },
    { id: '1h', label: '1 Hour' },
    { id: '4h', label: '4 Hours' },
    { id: '1d', label: '1 Day' },
    { id: '1w', label: '1 Week' }
  ];

  if (isCollapsed) {
    return (
      <div style={{
        width: '50px',
        height: '100%',
        backgroundColor: '#2c3e50',
        borderRight: '1px solid #34495e',
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        padding: '0.5rem 0'
      }}>
        <button
          onClick={onToggleCollapse}
          style={{
            background: 'none',
            border: 'none',
            cursor: 'pointer',
            fontSize: '1.2rem',
            color: '#ecf0f1',
            padding: '0.5rem',
            borderRadius: '4px',
            marginBottom: '1rem'
          }}
          title="Expand Navigation"
        >
          ▶
        </button>
        
        {/* Vertical mode indicators */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
          {modes.map((mode) => (
            <div
              key={mode.id}
              style={{
                fontSize: '1.5rem',
                padding: '0.5rem',
                borderRadius: '4px',
                backgroundColor: currentMode === mode.id ? '#3498db' : 'transparent',
                opacity: mode.available ? 1 : 0.3,
                cursor: mode.available ? 'pointer' : 'not-allowed'
              }}
              title={mode.label}
              onClick={() => mode.available && onModeChange(mode.id)}
            >
              {mode.icon}
            </div>
          ))}
        </div>
      </div>
    );
  }

  return (
    <div style={{
      width: '220px',
      height: '100%',
      backgroundColor: '#2c3e50',
      borderRight: '1px solid #34495e',
      display: 'flex',
      flexDirection: 'column',
      color: '#ecf0f1'
    }}>
      {/* Header */}
      <div style={{
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'center',
        padding: '1rem',
        borderBottom: '1px solid #34495e'
      }}>
        <h3 style={{ 
          margin: 0, 
          fontSize: '1rem',
          fontWeight: '600',
          color: '#ecf0f1'
        }}>
          Navigation
        </h3>
        <button
          onClick={onToggleCollapse}
          style={{
            background: 'none',
            border: 'none',
            cursor: 'pointer',
            fontSize: '1rem',
            color: '#bdc3c7',
            padding: '0.25rem'
          }}
          title="Collapse Navigation"
        >
          ◀
        </button>
      </div>

      {/* Mode Selection */}
      <div style={{ padding: '1rem' }}>
        <h4 style={{ 
          margin: '0 0 0.75rem 0', 
          fontSize: '0.85rem',
          fontWeight: '600',
          color: '#bdc3c7',
          textTransform: 'uppercase',
          letterSpacing: '0.5px'
        }}>
          Mode
        </h4>
        
        <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
          {modes.map((mode) => (
            <button
              key={mode.id}
              onClick={() => mode.available && onModeChange(mode.id)}
              disabled={!mode.available}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '0.75rem',
                padding: '0.75rem',
                backgroundColor: currentMode === mode.id ? '#3498db' : 'transparent',
                border: currentMode === mode.id ? '1px solid #5dade2' : '1px solid transparent',
                borderRadius: '6px',
                color: mode.available ? '#ecf0f1' : '#7f8c8d',
                cursor: mode.available ? 'pointer' : 'not-allowed',
                textAlign: 'left',
                fontSize: '0.9rem',
                transition: 'all 0.2s ease',
                opacity: mode.available ? 1 : 0.5
              }}
              title={mode.available ? mode.description : 'Coming soon'}
            >
              <span style={{ fontSize: '1.2rem' }}>{mode.icon}</span>
              <div>
                <div style={{ fontWeight: '500' }}>{mode.label}</div>
                {!mode.available && (
                  <div style={{ fontSize: '0.7rem', color: '#95a5a6' }}>
                    Coming Soon
                  </div>
                )}
              </div>
            </button>
          ))}
        </div>
      </div>

      {/* Timeframe Selection */}
      <div style={{ padding: '1rem', borderTop: '1px solid #34495e' }}>
        <h4 style={{ 
          margin: '0 0 0.75rem 0', 
          fontSize: '0.85rem',
          fontWeight: '600',
          color: '#bdc3c7',
          textTransform: 'uppercase',
          letterSpacing: '0.5px'
        }}>
          Timeframe
        </h4>
        
        <select
          value={selectedTimeframe}
          onChange={(e) => onTimeframeChange(e.target.value)}
          style={{
            width: '100%',
            padding: '0.6rem',
            backgroundColor: '#34495e',
            border: '1px solid #4a5568',
            borderRadius: '4px',
            color: '#ecf0f1',
            fontSize: '0.9rem',
            cursor: 'pointer'
          }}
        >
          {timeframes.map((tf) => (
            <option key={tf.id} value={tf.id} style={{ backgroundColor: '#34495e' }}>
              {tf.label}
            </option>
          ))}
        </select>
      </div>

      {/* Status/Info Section */}
      <div style={{ 
        marginTop: 'auto',
        padding: '1rem',
        borderTop: '1px solid #34495e',
        backgroundColor: '#34495e'
      }}>
        <div style={{ 
          fontSize: '0.8rem', 
          color: '#95a5a6',
          textAlign: 'center'
        }}>
          <div style={{ marginBottom: '0.5rem', fontWeight: '500' }}>
            KTRDR v1.0 MVP
          </div>
          <div>
            Research Phase
          </div>
        </div>
      </div>
    </div>
  );
};

export default LeftSidebar;