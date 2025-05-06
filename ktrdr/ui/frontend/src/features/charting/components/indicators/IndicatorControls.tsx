// filepath: /Users/karl/Documents/dev/ktrdr2/ktrdr/ui/frontend/src/components/charts/indicators/IndicatorControls.tsx
import React, { useState } from 'react';
import { 
  IndicatorConfig, 
  IndicatorMetadata,
  IndicatorParameter
} from '../../../types/data';
import { useTheme } from '../../layouts/ThemeProvider';
import './IndicatorControls.css';

interface IndicatorControlsProps {
  /** Indicator configuration to edit */
  config: IndicatorConfig;
  /** Metadata for this indicator type */
  metadata: IndicatorMetadata;
  /** Callback when configuration changes */
  onChange: (updatedConfig: IndicatorConfig) => void;
  /** Callback when indicator is removed */
  onRemove?: () => void;
}

/**
 * IndicatorControls component
 * 
 * Allows users to configure indicator parameters and styling.
 * Provides controls for adjusting periods, colors, line widths, etc.
 */
const IndicatorControls: React.FC<IndicatorControlsProps> = ({
  config,
  metadata,
  onChange,
  onRemove
}) => {
  const { theme } = useTheme();
  const isDarkTheme = theme === 'dark';
  const [expanded, setExpanded] = useState(false);
  
  // Update parameter value
  const handleParameterChange = (paramName: string, value: any) => {
    const updatedConfig = {
      ...config,
      parameters: {
        ...config.parameters,
        [paramName]: value
      }
    };
    onChange(updatedConfig);
  };
  
  // Update color value
  const handleColorChange = (index: number, color: string) => {
    const updatedColors = [...config.colors];
    updatedColors[index] = color;
    
    const updatedConfig = {
      ...config,
      colors: updatedColors
    };
    onChange(updatedConfig);
  };
  
  // Update line width
  const handleLineWidthChange = (index: number, width: number) => {
    const updatedLineWidths = [...config.lineWidths];
    updatedLineWidths[index] = width;
    
    const updatedConfig = {
      ...config,
      lineWidths: updatedLineWidths
    };
    onChange(updatedConfig);
  };
  
  // Update line style
  const handleLineStyleChange = (index: number, style: string) => {
    const updatedLineStyles = [...config.lineStyles];
    updatedLineStyles[index] = style;
    
    const updatedConfig = {
      ...config,
      lineStyles: updatedLineStyles
    };
    onChange(updatedConfig);
  };
  
  // Toggle visibility
  const handleVisibilityToggle = () => {
    const updatedConfig = {
      ...config,
      visible: !config.visible
    };
    onChange(updatedConfig);
  };
  
  // Render parameter control based on parameter type
  const renderParameterControl = (param: IndicatorParameter) => {
    const value = config.parameters[param.name];
    
    switch (param.type) {
      case 'number':
        return (
          <div className="indicator-control-item" key={param.name}>
            <label htmlFor={`param-${param.name}`}>{param.label}</label>
            <input
              id={`param-${param.name}`}
              type="number"
              value={value}
              min={param.min}
              max={param.max}
              step={param.step}
              onChange={(e) => handleParameterChange(param.name, parseFloat(e.target.value))}
            />
          </div>
        );
        
      case 'select':
        return (
          <div className="indicator-control-item" key={param.name}>
            <label htmlFor={`param-${param.name}`}>{param.label}</label>
            <select
              id={`param-${param.name}`}
              value={value}
              onChange={(e) => handleParameterChange(param.name, e.target.value)}
            >
              {param.options?.map(option => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
          </div>
        );
        
      case 'checkbox':
        return (
          <div className="indicator-control-item checkbox" key={param.name}>
            <label htmlFor={`param-${param.name}`}>
              <input
                id={`param-${param.name}`}
                type="checkbox"
                checked={value}
                onChange={(e) => handleParameterChange(param.name, e.target.checked)}
              />
              {param.label}
            </label>
          </div>
        );
        
      default:
        return null;
    }
  };
  
  // Get series names for styling controls
  const seriesNames = metadata.type === 'multi-line' && metadata.metadata?.names 
    ? metadata.metadata.names 
    : ['Series'];
  
  return (
    <div className={`indicator-controls ${isDarkTheme ? 'dark-theme' : 'light-theme'}`}>
      <div className="indicator-controls-header">
        <div className="indicator-controls-title-area">
          <div className="visibility-toggle">
            <input
              type="checkbox"
              id={`visibility-${config.id}`}
              checked={config.visible}
              onChange={handleVisibilityToggle}
            />
            <label htmlFor={`visibility-${config.id}`}></label>
          </div>
          
          <h3 className="indicator-controls-title">{metadata.name}</h3>
        </div>
        
        <div className="indicator-controls-actions">
          <button 
            className="toggle-expand-button"
            onClick={() => setExpanded(!expanded)}
            title={expanded ? "Collapse" : "Expand"}
          >
            {expanded ? '−' : '+'}
          </button>
          
          {onRemove && (
            <button 
              className="remove-button"
              onClick={onRemove}
              title="Remove indicator"
            >
              ✕
            </button>
          )}
        </div>
      </div>
      
      {expanded && (
        <div className="indicator-controls-content">
          <div className="indicator-parameters">
            <h4>Parameters</h4>
            {metadata.parameters.map(param => renderParameterControl(param))}
          </div>
          
          <div className="indicator-styling">
            <h4>Style</h4>
            {seriesNames.map((name, index) => (
              <div className="series-style-control" key={index}>
                <div className="series-name">{name}</div>
                
                <div className="style-controls">
                  <div className="color-picker">
                    <label htmlFor={`color-${config.id}-${index}`}>Color</label>
                    <input
                      id={`color-${config.id}-${index}`}
                      type="color"
                      value={config.colors[index] || '#1E88E5'}
                      onChange={(e) => handleColorChange(index, e.target.value)}
                    />
                  </div>
                  
                  <div className="line-width-control">
                    <label htmlFor={`width-${config.id}-${index}`}>Width</label>
                    <select
                      id={`width-${config.id}-${index}`}
                      value={config.lineWidths[index] || 2}
                      onChange={(e) => handleLineWidthChange(index, parseInt(e.target.value))}
                    >
                      <option value={1}>1</option>
                      <option value={2}>2</option>
                      <option value={3}>3</option>
                      <option value={4}>4</option>
                    </select>
                  </div>
                  
                  <div className="line-style-control">
                    <label htmlFor={`style-${config.id}-${index}`}>Style</label>
                    <select
                      id={`style-${config.id}-${index}`}
                      value={config.lineStyles[index] || '0'}
                      onChange={(e) => handleLineStyleChange(index, e.target.value)}
                    >
                      <option value="0">Solid</option>
                      <option value="1">Dotted</option>
                      <option value="2">Dashed</option>
                    </select>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
};

export default IndicatorControls;