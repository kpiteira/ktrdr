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
  isLoading: boolean;
  isCollapsed?: boolean;

  // Action props
  onAddSMA: () => void;
  onAddRSI: () => void;
  onRemoveIndicator: (id: string) => void;
  onToggleIndicator: (id: string) => void;
  onToggleParameterControls: (indicatorId: string) => void;
  onParameterUpdate: (indicatorId: string, parameterName: string, value: any) => void;
  onNewSMAPeriodChange: (period: number) => void;
  onNewRSIPeriodChange: (period: number) => void;
  onToggleCollapse?: () => void;
}

const IndicatorSidebar: FC<IndicatorSidebarProps> = ({
  indicators,
  expandedIndicators,
  localParameterValues,
  newSMAPeriod,
  newRSIPeriod,
  isLoading,
  isCollapsed = false,
  onAddSMA,
  onAddRSI,
  onRemoveIndicator,
  onToggleIndicator,
  onToggleParameterControls,
  onParameterUpdate,
  onNewSMAPeriodChange,
  onNewRSIPeriodChange,
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
            buttonColor="#9C27B0"
            isLoading={isLoading}
            onValueChange={onNewRSIPeriodChange}
            onAdd={onAddRSI}
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
            {indicator.displayName}({localParameterValues.period || indicator.parameters.period})
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
  onParameterUpdate: (parameterName: string, value: any) => void;
}

const ParameterControls: FC<ParameterControlsProps> = ({
  config,
  localValues,
  onParameterUpdate
}) => {
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
      </div>
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