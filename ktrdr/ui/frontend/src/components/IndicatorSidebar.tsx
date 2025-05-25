import React, { FC, useState, useEffect, useRef } from 'react';

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
  onUpdateIndicator?: (id: string, updates: Partial<IndicatorInfo>) => void;
  isCollapsed?: boolean;
  onToggleCollapse?: () => void;
  isLoading?: boolean;
}

const IndicatorSidebar: FC<IndicatorSidebarProps> = ({
  indicators,
  onAddIndicator,
  onRemoveIndicator,
  onToggleIndicator,
  onUpdateIndicator,
  isCollapsed = false,
  onToggleCollapse,
  isLoading = false
}) => {
  const [newSMAPeriod, setNewSMAPeriod] = useState(20);
  const [newRSIPeriod, setNewRSIPeriod] = useState(14);
  const [expandedIndicators, setExpandedIndicators] = useState<Set<string>>(new Set());
  const [localParameterValues, setLocalParameterValues] = useState<Record<string, {period: number, color: string}>>({});
  const initializedIndicatorsRef = useRef<Set<string>>(new Set());

  const handleAddSMA = () => {
    if (newSMAPeriod >= 2 && newSMAPeriod <= 500) {
      onAddIndicator('SMA', newSMAPeriod);
    }
  };

  const handleAddRSI = () => {
    if (newRSIPeriod >= 2 && newRSIPeriod <= 100) {
      onAddIndicator('RSI', newRSIPeriod);
    }
  };

  const toggleParameterControls = (indicatorId: string) => {
    setExpandedIndicators(prev => {
      const newSet = new Set(prev);
      if (newSet.has(indicatorId)) {
        newSet.delete(indicatorId);
      } else {
        newSet.add(indicatorId);
      }
      return newSet;
    });
  };

  // Initialize local parameter values when indicators change
  useEffect(() => {
    const newLocalValues: Record<string, {period: number, color: string}> = {};
    indicators.forEach(indicator => {
      // Only initialize if we haven't already initialized this indicator
      if (!initializedIndicatorsRef.current.has(indicator.id)) {
        newLocalValues[indicator.id] = {
          period: indicator.period,
          color: indicator.color
        };
        initializedIndicatorsRef.current.add(indicator.id);
      }
    });
    
    if (Object.keys(newLocalValues).length > 0) {
      console.log('[IndicatorSidebar] Initializing local values for new indicators:', newLocalValues);
      setLocalParameterValues(prev => ({ ...prev, ...newLocalValues }));
    }
  }, [indicators]);

  const handleParameterUpdate = (indicatorId: string, updates: Partial<IndicatorInfo>) => {
    console.log('[IndicatorSidebar] Parameter update:', indicatorId, updates);
    console.log('[IndicatorSidebar] Current local values:', localParameterValues);
    
    // Update local state immediately for responsive UI
    setLocalParameterValues(prev => {
      const newValues = {
        ...prev,
        [indicatorId]: {
          ...prev[indicatorId],
          ...updates
        }
      };
      console.log('[IndicatorSidebar] Updated local values:', newValues);
      return newValues;
    });
    
    // Update parent state
    if (onUpdateIndicator) {
      onUpdateIndicator(indicatorId, updates);
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
          <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
            {/* Trend Indicators */}
            {indicators.filter(ind => ind.type === 'SMA').length > 0 && (
              <div>
                <div style={{ fontSize: '0.8rem', color: '#666', marginBottom: '0.5rem', fontWeight: '500' }}>
                  Trend Indicators
                </div>
                <div style={{ display: 'flex', flexDirection: 'column', gap: '0.25rem' }}>
                  {indicators.filter(ind => ind.type === 'SMA').map((indicator) => (
                    <div key={indicator.id}>
                      <div
                        style={{
                          display: 'flex',
                          alignItems: 'center',
                          justifyContent: 'space-between',
                          padding: '0.5rem',
                          backgroundColor: '#fff',
                          border: '1px solid #e0e0e0',
                          borderRadius: expandedIndicators.has(indicator.id) ? '4px 4px 0 0' : '4px',
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
                            onClick={() => toggleParameterControls(indicator.id)}
                            style={{
                              background: 'none',
                              border: 'none',
                              cursor: 'pointer',
                              fontSize: '0.8rem',
                              color: '#666',
                              padding: '0.25rem'
                            }}
                            title="Parameters"
                          >
                            ⚙️
                          </button>
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
                      
                      {/* Parameter Controls */}
                      {expandedIndicators.has(indicator.id) && (
                        <div
                          style={{
                            padding: '0.75rem',
                            backgroundColor: '#f8f9fa',
                            border: '1px solid #e0e0e0',
                            borderTop: 'none',
                            borderRadius: '0 0 4px 4px',
                            fontSize: '0.8rem'
                          }}
                        >
                          <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
                            {/* Period Control */}
                            <div>
                              <label style={{ display: 'block', color: '#666', marginBottom: '0.25rem' }}>
                                Period:
                              </label>
                              <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                                <input
                                  type="range"
                                  min="2"
                                  max="200"
                                  value={localParameterValues[indicator.id]?.period ?? indicator.period}
                                  onChange={(e) => handleParameterUpdate(indicator.id, { period: parseInt(e.target.value) })}
                                  style={{ flex: 1 }}
                                />
                                <input
                                  type="number"
                                  min="2"
                                  max="200"
                                  value={localParameterValues[indicator.id]?.period ?? indicator.period}
                                  onChange={(e) => handleParameterUpdate(indicator.id, { period: parseInt(e.target.value) || (localParameterValues[indicator.id]?.period ?? indicator.period) })}
                                  style={{
                                    width: '50px',
                                    padding: '0.2rem',
                                    border: '1px solid #ccc',
                                    borderRadius: '3px',
                                    textAlign: 'center',
                                    fontSize: '0.8rem'
                                  }}
                                />
                              </div>
                            </div>
                            
                            {/* Color Control */}
                            <div>
                              <label style={{ display: 'block', color: '#666', marginBottom: '0.25rem' }}>
                                Color:
                              </label>
                              <input
                                type="color"
                                value={localParameterValues[indicator.id]?.color ?? indicator.color}
                                onChange={(e) => handleParameterUpdate(indicator.id, { color: e.target.value })}
                                style={{
                                  width: '40px',
                                  height: '24px',
                                  border: '1px solid #ccc',
                                  borderRadius: '3px',
                                  cursor: 'pointer'
                                }}
                              />
                            </div>
                          </div>
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Oscillator Indicators */}
            {indicators.filter(ind => ind.type === 'RSI').length > 0 && (
              <div>
                <div style={{ fontSize: '0.8rem', color: '#666', marginBottom: '0.5rem', fontWeight: '500' }}>
                  Oscillators
                </div>
                <div style={{ display: 'flex', flexDirection: 'column', gap: '0.25rem' }}>
                  {indicators.filter(ind => ind.type === 'RSI').map((indicator) => (
                    <div key={indicator.id}>
                      <div
                        style={{
                          display: 'flex',
                          alignItems: 'center',
                          justifyContent: 'space-between',
                          padding: '0.5rem',
                          backgroundColor: '#fff',
                          border: '1px solid #e0e0e0',
                          borderRadius: expandedIndicators.has(indicator.id) ? '4px 4px 0 0' : '4px',
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
                            onClick={() => toggleParameterControls(indicator.id)}
                            style={{
                              background: 'none',
                              border: 'none',
                              cursor: 'pointer',
                              fontSize: '0.8rem',
                              color: '#666',
                              padding: '0.25rem'
                            }}
                            title="Parameters"
                          >
                            ⚙️
                          </button>
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
                      
                      {/* Parameter Controls */}
                      {expandedIndicators.has(indicator.id) && (
                        <div
                          style={{
                            padding: '0.75rem',
                            backgroundColor: '#f8f9fa',
                            border: '1px solid #e0e0e0',
                            borderTop: 'none',
                            borderRadius: '0 0 4px 4px',
                            fontSize: '0.8rem'
                          }}
                        >
                          <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
                            {/* Period Control */}
                            <div>
                              <label style={{ display: 'block', color: '#666', marginBottom: '0.25rem' }}>
                                Period:
                              </label>
                              <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                                <input
                                  type="range"
                                  min="2"
                                  max="100"
                                  value={localParameterValues[indicator.id]?.period ?? indicator.period}
                                  onChange={(e) => handleParameterUpdate(indicator.id, { period: parseInt(e.target.value) })}
                                  style={{ flex: 1 }}
                                />
                                <input
                                  type="number"
                                  min="2"
                                  max="100"
                                  value={localParameterValues[indicator.id]?.period ?? indicator.period}
                                  onChange={(e) => handleParameterUpdate(indicator.id, { period: parseInt(e.target.value) || (localParameterValues[indicator.id]?.period ?? indicator.period) })}
                                  style={{
                                    width: '50px',
                                    padding: '0.2rem',
                                    border: '1px solid #ccc',
                                    borderRadius: '3px',
                                    textAlign: 'center',
                                    fontSize: '0.8rem'
                                  }}
                                />
                              </div>
                            </div>
                            
                            {/* Color Control */}
                            <div>
                              <label style={{ display: 'block', color: '#666', marginBottom: '0.25rem' }}>
                                Color:
                              </label>
                              <input
                                type="color"
                                value={localParameterValues[indicator.id]?.color ?? indicator.color}
                                onChange={(e) => handleParameterUpdate(indicator.id, { color: e.target.value })}
                                style={{
                                  width: '40px',
                                  height: '24px',
                                  border: '1px solid #ccc',
                                  borderRadius: '3px',
                                  cursor: 'pointer'
                                }}
                              />
                            </div>
                          </div>
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              </div>
            )}
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
        
        <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
          {/* SMA Section */}
          <div>
            <label style={{ 
              display: 'block', 
              fontSize: '0.8rem', 
              color: '#666', 
              marginBottom: '0.5rem',
              fontWeight: '500'
            }}>
              Trend: Simple Moving Average (SMA)
            </label>
            <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'center', marginBottom: '0.5rem' }}>
              <input
                type="number"
                min="2"
                max="500"
                value={newSMAPeriod}
                onChange={(e) => setNewSMAPeriod(parseInt(e.target.value) || 20)}
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
            <button
              onClick={handleAddSMA}
              disabled={isLoading || newSMAPeriod < 2 || newSMAPeriod > 500}
              style={{
                padding: '0.5rem 0.75rem',
                backgroundColor: isLoading ? '#ccc' : '#1976d2',
                color: 'white',
                border: 'none',
                borderRadius: '4px',
                cursor: isLoading ? 'not-allowed' : 'pointer',
                fontSize: '0.8rem',
                fontWeight: '500',
                width: '100%'
              }}
            >
              {isLoading ? 'Adding...' : `Add SMA(${newSMAPeriod})`}
            </button>
          </div>

          {/* RSI Section */}
          <div>
            <label style={{ 
              display: 'block', 
              fontSize: '0.8rem', 
              color: '#666', 
              marginBottom: '0.5rem',
              fontWeight: '500'
            }}>
              Oscillator: Relative Strength Index (RSI)
            </label>
            <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'center', marginBottom: '0.5rem' }}>
              <input
                type="number"
                min="2"
                max="100"
                value={newRSIPeriod}
                onChange={(e) => setNewRSIPeriod(parseInt(e.target.value) || 14)}
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
            <button
              onClick={handleAddRSI}
              disabled={isLoading || newRSIPeriod < 2 || newRSIPeriod > 100}
              style={{
                padding: '0.5rem 0.75rem',
                backgroundColor: isLoading ? '#ccc' : '#9C27B0',
                color: 'white',
                border: 'none',
                borderRadius: '4px',
                cursor: isLoading ? 'not-allowed' : 'pointer',
                fontSize: '0.8rem',
                fontWeight: '500',
                width: '100%'
              }}
            >
              {isLoading ? 'Adding...' : `Add RSI(${newRSIPeriod})`}
            </button>
          </div>
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