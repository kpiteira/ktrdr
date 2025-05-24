import { FC, useState } from 'react';

interface IndicatorInfo {
  id: string;
  type: string;
  period: number;
  color: string;
  visible: boolean;
}

interface IndicatorSidebarProps {
  indicators: IndicatorInfo[];
  onAddIndicator: (type: string, period: number) => void;
  onRemoveIndicator: (id: string) => void;
  onToggleIndicator: (id: string) => void;
  isCollapsed?: boolean;
  onToggleCollapse?: () => void;
  isLoading?: boolean;
}

const IndicatorSidebar: FC<IndicatorSidebarProps> = ({
  indicators,
  onAddIndicator,
  onRemoveIndicator,
  onToggleIndicator,
  isCollapsed = false,
  onToggleCollapse,
  isLoading = false
}) => {
  const [newIndicatorPeriod, setNewIndicatorPeriod] = useState(20);

  const handleAddSMA = () => {
    if (newIndicatorPeriod >= 2 && newIndicatorPeriod <= 500) {
      onAddIndicator('SMA', newIndicatorPeriod);
    }
  };

  if (isCollapsed) {
    return (
      <div style={{
        width: '40px',
        height: '100%',
        backgroundColor: '#f8f9fa',
        borderRight: '1px solid #e0e0e0',
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
            color: '#666',
            padding: '0.5rem',
            borderRadius: '4px'
          }}
          title="Expand Sidebar"
        >
          ▶
        </button>
      </div>
    );
  }

  return (
    <div style={{
      width: '280px',
      height: '100%',
      backgroundColor: '#f8f9fa',
      borderRight: '1px solid #e0e0e0',
      display: 'flex',
      flexDirection: 'column',
      padding: '1rem'
    }}>
      {/* Header */}
      <div style={{
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'center',
        marginBottom: '1rem',
        paddingBottom: '0.5rem',
        borderBottom: '1px solid #e0e0e0'
      }}>
        <h3 style={{ margin: 0, color: '#333', fontSize: '1.1rem' }}>
          Indicators
        </h3>
        {onToggleCollapse && (
          <button
            onClick={onToggleCollapse}
            style={{
              background: 'none',
              border: 'none',
              cursor: 'pointer',
              fontSize: '1rem',
              color: '#666',
              padding: '0.25rem'
            }}
            title="Collapse Sidebar"
          >
            ◀
          </button>
        )}
      </div>

      {/* Active Indicators List */}
      <div style={{ marginBottom: '1.5rem' }}>
        <h4 style={{ 
          margin: '0 0 0.75rem 0', 
          color: '#555', 
          fontSize: '0.9rem',
          fontWeight: '600'
        }}>
          Active Indicators ({indicators.length})
        </h4>
        
        {indicators.length === 0 ? (
          <div style={{
            padding: '1rem',
            backgroundColor: '#fff',
            border: '1px dashed #ccc',
            borderRadius: '4px',
            textAlign: 'center',
            color: '#666',
            fontSize: '0.85rem'
          }}>
            No indicators added yet
          </div>
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
            {indicators.map((indicator) => (
              <div
                key={indicator.id}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  padding: '0.75rem',
                  backgroundColor: '#fff',
                  border: '1px solid #e0e0e0',
                  borderRadius: '4px',
                  fontSize: '0.85rem'
                }}
              >
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                  <div
                    style={{
                      width: '12px',
                      height: '12px',
                      backgroundColor: indicator.color,
                      borderRadius: '2px'
                    }}
                  />
                  <span style={{ fontWeight: '500' }}>
                    {indicator.type}({indicator.period})
                  </span>
                </div>
                
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.25rem' }}>
                  <button
                    onClick={() => onToggleIndicator(indicator.id)}
                    style={{
                      background: 'none',
                      border: 'none',
                      cursor: 'pointer',
                      fontSize: '0.8rem',
                      color: indicator.visible ? '#4CAF50' : '#999',
                      padding: '0.25rem'
                    }}
                    title={indicator.visible ? 'Hide' : 'Show'}
                  >
                    {indicator.visible ? '👁' : '🚫'}
                  </button>
                  <button
                    onClick={() => onRemoveIndicator(indicator.id)}
                    style={{
                      background: 'none',
                      border: 'none',
                      cursor: 'pointer',
                      fontSize: '0.8rem',
                      color: '#f44336',
                      padding: '0.25rem'
                    }}
                    title="Remove"
                  >
                    ✕
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Add Indicator Section */}
      <div style={{
        padding: '1rem',
        backgroundColor: '#fff',
        border: '1px solid #e0e0e0',
        borderRadius: '4px'
      }}>
        <h4 style={{ 
          margin: '0 0 0.75rem 0', 
          color: '#555', 
          fontSize: '0.9rem',
          fontWeight: '600'
        }}>
          Add Indicator
        </h4>
        
        <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
          <div>
            <label style={{ 
              display: 'block', 
              fontSize: '0.8rem', 
              color: '#666', 
              marginBottom: '0.25rem' 
            }}>
              Simple Moving Average (SMA)
            </label>
            <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'center' }}>
              <input
                type="number"
                min="2"
                max="500"
                value={newIndicatorPeriod}
                onChange={(e) => setNewIndicatorPeriod(parseInt(e.target.value) || 20)}
                style={{
                  width: '60px',
                  padding: '0.4rem',
                  border: '1px solid #ccc',
                  borderRadius: '3px',
                  textAlign: 'center',
                  fontSize: '0.85rem'
                }}
                disabled={isLoading}
              />
              <span style={{ fontSize: '0.8rem', color: '#666' }}>periods</span>
            </div>
          </div>
          
          <button
            onClick={handleAddSMA}
            disabled={isLoading || newIndicatorPeriod < 2 || newIndicatorPeriod > 500}
            style={{
              padding: '0.6rem 1rem',
              backgroundColor: isLoading ? '#ccc' : '#1976d2',
              color: 'white',
              border: 'none',
              borderRadius: '4px',
              cursor: isLoading ? 'not-allowed' : 'pointer',
              fontSize: '0.85rem',
              fontWeight: '500'
            }}
          >
            {isLoading ? 'Adding...' : `Add SMA(${newIndicatorPeriod})`}
          </button>
        </div>
      </div>

      {/* Future: More indicator types will go here */}
      <div style={{ 
        marginTop: '1rem', 
        padding: '0.75rem', 
        backgroundColor: '#f0f0f0', 
        borderRadius: '4px',
        fontSize: '0.8rem',
        color: '#666',
        textAlign: 'center'
      }}>
        More indicators coming soon...
        <br />
        (RSI, MACD, EMA, etc.)
      </div>
    </div>
  );
};

export default IndicatorSidebar;