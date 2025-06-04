import React, { FC } from 'react';
import { IndicatorInfo, getIndicatorConfig, INDICATOR_REGISTRY } from '../../../store/indicatorRegistry';

/**
 * Pure presentation component for the indicator sidebar
 * 
 * This component receives all data and callbacks as props and focuses
 * purely on rendering the UI. No state management or business logic.
 */

interface IndicatorSidebarProps {
  // Data props
  indicators: IndicatorInfo[];
  expandedIndicators: Set<string>;
  localParameterValues: Record<string, Record<string, any>>;
  newSMAPeriod: number;
  newRSIPeriod: number;
  newMACDFastPeriod: number;
  newMACDSlowPeriod: number;
  newMACDSignalPeriod: number;
  newZigZagThreshold: number;
  isLoading: boolean;
  isCollapsed?: boolean;

  // Action props
  onAddSMA: () => void;
  onAddRSI: () => void;
  onAddMACD: () => void;
  onAddZigZag: () => void;
  onRemoveIndicator: (id: string) => void;
  onToggleIndicator: (id: string) => void;
  onToggleParameterControls: (indicatorId: string) => void;
  onParameterUpdate: (indicatorId: string, parameterName: string, value: any) => void;
  onNewSMAPeriodChange: (period: number) => void;
  onNewRSIPeriodChange: (period: number) => void;
  onNewMACDFastPeriodChange: (period: number) => void;
  onNewMACDSlowPeriodChange: (period: number) => void;
  onNewMACDSignalPeriodChange: (period: number) => void;
  onNewZigZagThresholdChange: (threshold: number) => void;
  onToggleCollapse?: () => void;
}

const IndicatorSidebar: FC<IndicatorSidebarProps> = ({
  indicators,
  expandedIndicators,
  localParameterValues,
  newSMAPeriod,
  newRSIPeriod,
  newMACDFastPeriod,
  newMACDSlowPeriod,
  newMACDSignalPeriod,
  newZigZagThreshold,
  isLoading,
  isCollapsed = false,
  onAddSMA,
  onAddRSI,
  onAddMACD,
  onAddZigZag,
  onRemoveIndicator,
  onToggleIndicator,
  onToggleParameterControls,
  onParameterUpdate,
  onNewSMAPeriodChange,
  onNewRSIPeriodChange,
  onNewMACDFastPeriodChange,
  onNewMACDSlowPeriodChange,
  onNewMACDSignalPeriodChange,
  onNewZigZagThresholdChange,
  onToggleCollapse
}) => {
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

  // Group indicators by category for display
  const groupedIndicators = indicators.reduce((acc, indicator) => {
    const config = getIndicatorConfig(indicator.name);
    const category = config?.category || 'Other';
    if (!acc[category]) acc[category] = [];
    acc[category].push(indicator);
    return acc;
  }, {} as Record<string, IndicatorInfo[]>);

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
            {Object.entries(groupedIndicators).map(([category, categoryIndicators]) => (
              <div key={category}>
                <div style={{ fontSize: '0.8rem', color: '#666', marginBottom: '0.5rem', fontWeight: '500' }}>
                  {category}
                </div>
                <div style={{ display: 'flex', flexDirection: 'column', gap: '0.25rem' }}>
                  {categoryIndicators.map((indicator) => (
                    <IndicatorItem
                      key={indicator.id}
                      indicator={indicator}
                      isExpanded={expandedIndicators.has(indicator.id)}
                      localParameterValues={localParameterValues[indicator.id] || indicator.parameters}
                      onToggleParameterControls={() => onToggleParameterControls(indicator.id)}
                      onToggleIndicator={() => onToggleIndicator(indicator.id)}
                      onRemoveIndicator={() => onRemoveIndicator(indicator.id)}
                      onParameterUpdate={(parameterName, value) => onParameterUpdate(indicator.id, parameterName, value)}
                    />
                  ))}
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
        
        <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
          {/* SMA Section */}
          <IndicatorAddSection
            label="Trend: Simple Moving Average (SMA)"
            value={newSMAPeriod}
            min={2}
            max={500}
            unit="periods"
            buttonLabel={`Add SMA(${newSMAPeriod})`}
            buttonColor="#1976d2"
            isLoading={isLoading}
            onValueChange={onNewSMAPeriodChange}
            onAdd={onAddSMA}
          />

          {/* RSI Section */}
          <IndicatorAddSection
            label="Oscillator: Relative Strength Index (RSI)"
            value={newRSIPeriod}
            min={2}
            max={100}
            unit="periods"
            buttonLabel={`Add RSI(${newRSIPeriod})`}
            buttonColor="#FF5722"
            isLoading={isLoading}
            onValueChange={onNewRSIPeriodChange}
            onAdd={onAddRSI}
          />

          {/* MACD Section */}
          <MACDAddSection
            fastPeriod={newMACDFastPeriod}
            slowPeriod={newMACDSlowPeriod}
            signalPeriod={newMACDSignalPeriod}
            isLoading={isLoading}
            onFastPeriodChange={onNewMACDFastPeriodChange}
            onSlowPeriodChange={onNewMACDSlowPeriodChange}
            onSignalPeriodChange={onNewMACDSignalPeriodChange}
            onAdd={onAddMACD}
          />

          {/* ZigZag Section */}
          <IndicatorAddSection
            label="Pattern: ZigZag Analysis"
            value={newZigZagThreshold * 100} // Convert to percentage for display
            min={1}
            max={50}
            unit="% threshold"
            buttonLabel={`Add ZigZag(${(newZigZagThreshold * 100).toFixed(1)}%)`}
            buttonColor="#FF6B35"
            isLoading={isLoading}
            onValueChange={(value) => onNewZigZagThresholdChange(value / 100)} // Convert back to decimal
            onAdd={onAddZigZag}
          />
        </div>
      </div>

      {/* Future indicators notice */}
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
        (MACD, EMA, Bollinger Bands, etc.)
      </div>
    </div>
  );
};

/**
 * Individual indicator item component
 */
interface IndicatorItemProps {
  indicator: IndicatorInfo;
  isExpanded: boolean;
  localParameterValues: Record<string, any>;
  onToggleParameterControls: () => void;
  onToggleIndicator: () => void;
  onRemoveIndicator: () => void;
  onParameterUpdate: (parameterName: string, value: any) => void;
}

const IndicatorItem: FC<IndicatorItemProps> = ({
  indicator,
  isExpanded,
  localParameterValues,
  onToggleParameterControls,
  onToggleIndicator,
  onRemoveIndicator,
  onParameterUpdate
}) => {
  const config = getIndicatorConfig(indicator.name);
  if (!config) return null;

  return (
    <div>
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          padding: '0.5rem',
          backgroundColor: '#fff',
          border: '1px solid #e0e0e0',
          borderRadius: isExpanded ? '4px 4px 0 0' : '4px',
          fontSize: '0.85rem'
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
          <div
            style={{
              width: '12px',
              height: '12px',
              backgroundColor: localParameterValues.color || indicator.parameters.color,
              borderRadius: '2px'
            }}
          />
          <span style={{ fontWeight: '500' }}>
            {indicator.name === 'zigzag' 
              ? `${indicator.displayName}(${((localParameterValues.threshold || indicator.parameters.threshold) * 100).toFixed(1)}%)`
              : indicator.name === 'macd'
              ? `${indicator.displayName}(${localParameterValues.fast_period || indicator.parameters.fast_period},${localParameterValues.slow_period || indicator.parameters.slow_period},${localParameterValues.signal_period || indicator.parameters.signal_period})`
              : `${indicator.displayName}(${localParameterValues.period || indicator.parameters.period})`
            }
          </span>
        </div>
        
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.25rem' }}>
          <button
            onClick={onToggleParameterControls}
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
            onClick={onToggleIndicator}
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
            onClick={onRemoveIndicator}
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
      {isExpanded && (
        <ParameterControls
          config={config}
          localValues={localParameterValues}
          indicator={indicator}
          onParameterUpdate={onParameterUpdate}
        />
      )}
    </div>
  );
};

/**
 * Parameter controls component
 */
interface ParameterControlsProps {
  config: any;
  localValues: Record<string, any>;
  indicator: IndicatorInfo;
  onParameterUpdate: (parameterName: string, value: any) => void;
}

const ParameterControls: FC<ParameterControlsProps> = ({
  config,
  localValues,
  indicator,
  onParameterUpdate
}) => {
  // Check if this indicator supports fuzzy overlays based on registry configuration
  const supportsFuzzy = config?.fuzzySupport?.enabled || false;

  return (
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
        {/* Standard indicator parameters */}
        {config.parameterDefinitions.map((paramDef: any) => (
          <div key={paramDef.name}>
            <label style={{ display: 'block', color: '#666', marginBottom: '0.25rem' }}>
              {paramDef.label || paramDef.name}:
            </label>
            {paramDef.type === 'number' && (
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                <input
                  type="range"
                  min={paramDef.min}
                  max={paramDef.max}
                  step={paramDef.step}
                  value={localValues[paramDef.name] ?? paramDef.default}
                  onChange={(e) => onParameterUpdate(paramDef.name, parseInt(e.target.value))}
                  style={{ flex: 1 }}
                />
                <input
                  type="number"
                  min={paramDef.min}
                  max={paramDef.max}
                  value={localValues[paramDef.name] ?? paramDef.default}
                  onChange={(e) => onParameterUpdate(paramDef.name, parseInt(e.target.value) || paramDef.default)}
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
            )}
            {paramDef.type === 'select' && (
              <select
                value={localValues[paramDef.name] ?? paramDef.default}
                onChange={(e) => onParameterUpdate(paramDef.name, e.target.value)}
                style={{
                  padding: '0.3rem',
                  border: '1px solid #ccc',
                  borderRadius: '3px',
                  fontSize: '0.8rem',
                  width: '100%'
                }}
              >
                {paramDef.options.map((option: string) => (
                  <option key={option} value={option}>
                    {option}
                  </option>
                ))}
              </select>
            )}
            {paramDef.type === 'color' && (
              <input
                type="color"
                value={localValues[paramDef.name] ?? paramDef.default}
                onChange={(e) => onParameterUpdate(paramDef.name, e.target.value)}
                style={{
                  width: '40px',
                  height: '24px',
                  border: '1px solid #ccc',
                  borderRadius: '3px',
                  cursor: 'pointer'
                }}
              />
            )}
          </div>
        ))}

        {/* Fuzzy overlay controls - only shown for supported indicators */}
        {supportsFuzzy && (
          <>
            <div style={{ 
              borderTop: '1px solid #ddd', 
              marginTop: '0.5rem', 
              paddingTop: '0.5rem' 
            }}>
              <label style={{ 
                display: 'block', 
                color: '#666', 
                marginBottom: '0.5rem',
                fontWeight: '600',
                fontSize: '0.75rem'
              }}>
                🔮 Fuzzy Overlays
              </label>
              
              {/* Fuzzy visibility toggle */}
              <div style={{ marginBottom: '0.5rem' }}>
                <label style={{ 
                  display: 'flex', 
                  alignItems: 'center', 
                  gap: '0.5rem',
                  cursor: 'pointer'
                }}>
                  <input
                    type="checkbox"
                    checked={indicator.fuzzyVisible || false}
                    onChange={(e) => onParameterUpdate('fuzzyVisible', e.target.checked)}
                    style={{ cursor: 'pointer' }}
                  />
                  <span style={{ fontSize: '0.75rem', color: '#555' }}>
                    Show fuzzy membership
                  </span>
                </label>
              </div>

              {/* Fuzzy opacity slider - only shown when fuzzy is visible */}
              {indicator.fuzzyVisible && (
                <div style={{ marginBottom: '0.5rem' }}>
                  <label style={{ display: 'block', color: '#666', marginBottom: '0.25rem', fontSize: '0.75rem' }}>
                    Opacity: {Math.round((indicator.fuzzyOpacity || 0.3) * 100)}%
                  </label>
                  <input
                    type="range"
                    min={0.1}
                    max={1.0}
                    step={0.1}
                    value={indicator.fuzzyOpacity || 0.3}
                    onChange={(e) => onParameterUpdate('fuzzyOpacity', parseFloat(e.target.value))}
                    onMouseDown={(e) => e.stopPropagation()}
                    onTouchStart={(e) => e.stopPropagation()}
                    style={{ width: '100%' }}
                  />
                </div>
              )}

              {/* Color scheme selector - only shown when fuzzy is visible */}
              {indicator.fuzzyVisible && (
                <div>
                  <label style={{ display: 'block', color: '#666', marginBottom: '0.25rem', fontSize: '0.75rem' }}>
                    Color scheme:
                  </label>
                  <select
                    value={indicator.fuzzyColorScheme || 'default'}
                    onChange={(e) => onParameterUpdate('fuzzyColorScheme', e.target.value)}
                    style={{
                      padding: '0.25rem',
                      border: '1px solid #ccc',
                      borderRadius: '3px',
                      fontSize: '0.75rem',
                      width: '100%'
                    }}
                  >
                    <option value="default">Default (Blue/Gray/Red)</option>
                    <option value="monochrome">Monochrome (Grayscale)</option>
                    <option value="trading">Trading (Red/Green)</option>
                  </select>
                </div>
              )}
            </div>
          </>
        )}
      </div>
    </div>
  );
};

/**
 * MACD add section component for multi-parameter indicators
 */
interface MACDAddSectionProps {
  fastPeriod: number;
  slowPeriod: number;
  signalPeriod: number;
  isLoading: boolean;
  onFastPeriodChange: (period: number) => void;
  onSlowPeriodChange: (period: number) => void;
  onSignalPeriodChange: (period: number) => void;
  onAdd: () => void;
}

const MACDAddSection: FC<MACDAddSectionProps> = ({
  fastPeriod,
  slowPeriod,
  signalPeriod,
  isLoading,
  onFastPeriodChange,
  onSlowPeriodChange,
  onSignalPeriodChange,
  onAdd
}) => {
  // Validation: fast period must be less than slow period
  const isValid = fastPeriod < slowPeriod && 
                 fastPeriod >= 2 && fastPeriod <= 50 &&
                 slowPeriod >= 5 && slowPeriod <= 100 &&
                 signalPeriod >= 2 && signalPeriod <= 50;

  return (
    <div>
      <label style={{ 
        display: 'block', 
        fontSize: '0.8rem', 
        color: '#666', 
        marginBottom: '0.5rem',
        fontWeight: '500'
      }}>
        Oscillator: MACD (Moving Average Convergence Divergence)
      </label>
      
      {/* Parameter inputs in a grid */}
      <div style={{ 
        display: 'grid', 
        gridTemplateColumns: '1fr 1fr 1fr', 
        gap: '0.5rem', 
        marginBottom: '0.5rem' 
      }}>
        {/* Fast Period */}
        <div>
          <label style={{ 
            display: 'block', 
            fontSize: '0.7rem', 
            color: '#777', 
            marginBottom: '0.25rem',
            textAlign: 'center'
          }}>
            Fast
          </label>
          <input
            type="number"
            min={2}
            max={50}
            value={fastPeriod}
            onChange={(e) => onFastPeriodChange(parseInt(e.target.value) || 2)}
            style={{
              width: '100%',
              padding: '0.4rem',
              border: '1px solid #ccc',
              borderRadius: '3px',
              textAlign: 'center',
              fontSize: '0.8rem'
            }}
            disabled={isLoading}
          />
        </div>

        {/* Slow Period */}
        <div>
          <label style={{ 
            display: 'block', 
            fontSize: '0.7rem', 
            color: '#777', 
            marginBottom: '0.25rem',
            textAlign: 'center'
          }}>
            Slow
          </label>
          <input
            type="number"
            min={5}
            max={100}
            value={slowPeriod}
            onChange={(e) => onSlowPeriodChange(parseInt(e.target.value) || 5)}
            style={{
              width: '100%',
              padding: '0.4rem',
              border: '1px solid #ccc',
              borderRadius: '3px',
              textAlign: 'center',
              fontSize: '0.8rem'
            }}
            disabled={isLoading}
          />
        </div>

        {/* Signal Period */}
        <div>
          <label style={{ 
            display: 'block', 
            fontSize: '0.7rem', 
            color: '#777', 
            marginBottom: '0.25rem',
            textAlign: 'center'
          }}>
            Signal
          </label>
          <input
            type="number"
            min={2}
            max={50}
            value={signalPeriod}
            onChange={(e) => onSignalPeriodChange(parseInt(e.target.value) || 2)}
            style={{
              width: '100%',
              padding: '0.4rem',
              border: '1px solid #ccc',
              borderRadius: '3px',
              textAlign: 'center',
              fontSize: '0.8rem'
            }}
            disabled={isLoading}
          />
        </div>
      </div>

      {/* Validation feedback */}
      {!isValid && (
        <div style={{
          fontSize: '0.7rem',
          color: '#f44336',
          marginBottom: '0.5rem',
          textAlign: 'center'
        }}>
          {fastPeriod >= slowPeriod ? 'Fast period must be less than slow period' : 'Invalid parameter ranges'}
        </div>
      )}

      <button
        onClick={onAdd}
        disabled={isLoading || !isValid}
        style={{
          padding: '0.5rem 0.75rem',
          backgroundColor: isLoading || !isValid ? '#ccc' : '#9C27B0',
          color: 'white',
          border: 'none',
          borderRadius: '4px',
          cursor: isLoading || !isValid ? 'not-allowed' : 'pointer',
          fontSize: '0.8rem',
          fontWeight: '500',
          width: '100%'
        }}
      >
        {isLoading ? 'Adding...' : `Add MACD(${fastPeriod},${slowPeriod},${signalPeriod})`}
      </button>
    </div>
  );
};

/**
 * Add indicator section component
 */
interface IndicatorAddSectionProps {
  label: string;
  value: number;
  min: number;
  max: number;
  unit: string;
  buttonLabel: string;
  buttonColor: string;
  isLoading: boolean;
  onValueChange: (value: number) => void;
  onAdd: () => void;
}

const IndicatorAddSection: FC<IndicatorAddSectionProps> = ({
  label,
  value,
  min,
  max,
  unit,
  buttonLabel,
  buttonColor,
  isLoading,
  onValueChange,
  onAdd
}) => {
  return (
    <div>
      <label style={{ 
        display: 'block', 
        fontSize: '0.8rem', 
        color: '#666', 
        marginBottom: '0.5rem',
        fontWeight: '500'
      }}>
        {label}
      </label>
      <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'center', marginBottom: '0.5rem' }}>
        <input
          type="number"
          min={min}
          max={max}
          value={value}
          onChange={(e) => onValueChange(parseInt(e.target.value) || min)}
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
        <span style={{ fontSize: '0.8rem', color: '#666' }}>{unit}</span>
      </div>
      <button
        onClick={onAdd}
        disabled={isLoading || value < min || value > max}
        style={{
          padding: '0.5rem 0.75rem',
          backgroundColor: isLoading ? '#ccc' : buttonColor,
          color: 'white',
          border: 'none',
          borderRadius: '4px',
          cursor: isLoading ? 'not-allowed' : 'pointer',
          fontSize: '0.8rem',
          fontWeight: '500',
          width: '100%'
        }}
      >
        {isLoading ? 'Adding...' : buttonLabel}
      </button>
    </div>
  );
};

export default IndicatorSidebar;
