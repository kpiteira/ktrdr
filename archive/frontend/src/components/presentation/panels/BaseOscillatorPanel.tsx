/**
 * BaseOscillatorPanel - Generic panel component for oscillator indicators
 * 
 * This is the foundation component for all oscillator panels (RSI, MACD, Stochastic, etc.).
 * It provides common functionality while allowing for indicator-specific customization.
 */

import { FC, useRef, useCallback, useEffect, useState } from 'react';
import { IChartApi } from 'lightweight-charts';
import { IPanelComponent } from '../../../types/panels';
import OscillatorChart, { OscillatorData } from '../charts/OscillatorChart';
import { createLogger } from '../../../utils/logger';

// Add CSS animations for loading states
const panelAnimationStyles = `
  @keyframes pulse {
    0%, 100% { opacity: 1; }
    50% { opacity: 0.5; }
  }
  
  @keyframes loading-bar {
    0% { transform: translateX(-100%); }
    50% { transform: translateX(0%); }
    100% { transform: translateX(100%); }
  }
`;

// Inject styles if not already present
if (typeof document !== 'undefined' && !document.getElementById('panel-animations')) {
  const styleElement = document.createElement('style');
  styleElement.id = 'panel-animations';
  styleElement.textContent = panelAnimationStyles;
  document.head.appendChild(styleElement);
}

const logger = createLogger('BaseOscillatorPanel');

/**
 * Props specific to BaseOscillatorPanel
 */
interface BaseOscillatorPanelProps extends IPanelComponent {
  /** Data for the oscillator chart */
  oscillatorData?: OscillatorData;
  /** Loading state */
  isLoading?: boolean;
  /** Error message */
  error?: string;
  /** Fuzzy overlay data */
  fuzzyData?: any;
  /** Fuzzy overlay visibility */
  fuzzyVisible?: boolean;
  /** Fuzzy overlay opacity */
  fuzzyOpacity?: number;
  /** Fuzzy color scheme */
  fuzzyColorScheme?: string;
  /** Chart synchronization callbacks */
  onChartCreated?: (chart: IChartApi) => void;
  onChartDestroyed?: () => void;
  onCrosshairMove?: (params: any) => void;
  /** Whether to preserve time scale during updates */
  preserveTimeScale?: boolean;
}

/**
 * BaseOscillatorPanel component
 */
const BaseOscillatorPanel: FC<BaseOscillatorPanelProps> = ({
  state,
  indicators,
  lifecycle,
  width,
  height,
  actions,
  oscillatorData,
  isLoading = false,
  error,
  fuzzyData,
  fuzzyVisible = false,
  fuzzyOpacity = 0.3,
  fuzzyColorScheme = 'default',
  onChartCreated,
  onChartDestroyed,
  onCrosshairMove,
  preserveTimeScale = true
}) => {
  // Panel references
  const panelRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const resizeObserverRef = useRef<ResizeObserver | null>(null);
  
  // Local panel state
  const [actualHeight, setActualHeight] = useState(height);
  const [isResizing, setIsResizing] = useState(false);

  /**
   * Handle chart creation and lifecycle
   */
  const handleChartCreated = useCallback((chart: IChartApi) => {
    chartRef.current = chart;
    
    // Notify parent components
    if (onChartCreated) {
      onChartCreated(chart);
    }
    
    // Notify lifecycle
    if (lifecycle.onChartReady) {
      lifecycle.onChartReady(state.id, chart);
    }
    
    logger.debug(`Chart created for panel ${state.id} (${state.config.type})`);
  }, [state.id, state.config.type, onChartCreated, lifecycle]);

  /**
   * Handle chart destruction and cleanup
   */
  const handleChartDestroyed = useCallback(() => {
    if (chartRef.current) {
      logger.debug(`Chart destroyed for panel ${state.id}`);
      chartRef.current = null;
    }
    
    if (onChartDestroyed) {
      onChartDestroyed();
    }
  }, [state.id, onChartDestroyed]);

  /**
   * Handle crosshair synchronization
   */
  const handleCrosshairMove = useCallback((params: any) => {
    if (onCrosshairMove) {
      onCrosshairMove(params);
    }
  }, [onCrosshairMove]);

  /**
   * Handle panel resize
   */
  const handleResize = useCallback(() => {
    if (!panelRef.current || isResizing || state.isCollapsed) return;
    
    const rect = panelRef.current.getBoundingClientRect();
    const newHeight = rect.height;
    
    // Only update actualHeight if the change is significant and we're not collapsed
    if (Math.abs(newHeight - actualHeight) > 10) { // Increased threshold to prevent minor fluctuations
      setIsResizing(true);
      setActualHeight(newHeight);
      
      // Debounce resize completion
      setTimeout(() => {
        setIsResizing(false);
      }, 200); // Increased timeout for more stability
    }
  }, [actualHeight, isResizing, state.isCollapsed]);

  /**
   * Panel collapse/expand handler
   */
  const handleToggleCollapse = useCallback(() => {
    actions.toggleCollapse();
    
    // Update local state to reflect collapse
    setTimeout(() => {
      handleResize();
    }, 300); // Wait for CSS animation
  }, [actions, handleResize]);

  /**
   * Panel removal handler
   */
  const handleRemove = useCallback(() => {
    if (window.confirm(`Remove ${state.config.title} panel?`)) {
      actions.remove();
    }
  }, [actions, state.config.title]);

  /**
   * Setup resize observer
   */
  useEffect(() => {
    if (!panelRef.current) return;
    
    resizeObserverRef.current = new ResizeObserver(() => {
      handleResize();
    });
    
    resizeObserverRef.current.observe(panelRef.current);
    
    return () => {
      if (resizeObserverRef.current) {
        resizeObserverRef.current.disconnect();
      }
    };
  }, [handleResize]);

  /**
   * Update height when props change (with debouncing)
   */
  useEffect(() => {
    if (state.isCollapsed) return;
    
    if (Math.abs(height - actualHeight) > 5) {
      // Small debounce to prevent rapid height changes
      const timeoutId = setTimeout(() => {
        setActualHeight(height);
      }, 50);
      
      return () => clearTimeout(timeoutId);
    }
  }, [height, state.isCollapsed, actualHeight]);

  /**
   * Get display height based on collapse state
   * Use the configured height instead of actualHeight to prevent feedback loops
   */
  const displayHeight = state.isCollapsed ? 40 : height;

  /**
   * Generate oscillator configuration for this panel
   */
  const oscillatorConfig = {
    title: state.config.title,
    yAxisRange: state.config.yAxisConfig.type === 'fixed' 
      ? state.config.yAxisConfig.range 
      : undefined,
    referenceLines: state.config.yAxisConfig.referenceLines || []
  };

  return (
    <div
      ref={panelRef}
      style={{
        width: '100%',
        height: `${displayHeight}px`,
        minHeight: state.isCollapsed ? '40px' : '120px',
        backgroundColor: '#ffffff',
        border: '1px solid #e0e0e0',
        borderRadius: '8px',
        overflow: 'hidden',
        boxShadow: state.isCollapsed 
          ? '0 2px 6px rgba(0, 0, 0, 0.06)' 
          : '0 4px 12px rgba(0, 0, 0, 0.1)',
        transition: 'all 0.3s cubic-bezier(0.4, 0, 0.2, 1)',
        display: 'flex',
        flexDirection: 'column',
        transform: state.isCollapsed ? 'scale(0.99)' : 'scale(1)',
        borderColor: state.isCollapsed ? '#e0e0e0' : '#d0d0d0',
        marginBottom: '0.75rem'
      }}
      data-panel-id={state.id}
      data-panel-type={state.config.type}
    >
      {/* Panel Header */}
      <div
        style={{
          height: '40px',
          background: state.isCollapsed 
            ? 'linear-gradient(135deg, #f8f9fa 0%, #e9ecef 100%)'
            : 'linear-gradient(135deg, #ffffff 0%, #f8f9fa 100%)',
          borderBottom: state.isCollapsed ? 'none' : '1px solid #e9ecef',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          padding: '0 1rem',
          fontSize: '0.9rem',
          fontWeight: '600',
          color: '#2c3e50',
          flexShrink: 0,
          cursor: state.config.collapsible ? 'pointer' : 'default',
          transition: 'all 0.2s ease',
          backdropFilter: 'blur(10px)'
        }}
        onClick={state.config.collapsible ? handleToggleCollapse : undefined}
        onMouseEnter={(e) => {
          if (state.config.collapsible) {
            e.currentTarget.style.background = 'linear-gradient(135deg, #e9ecef 0%, #dee2e6 100%)';
          }
        }}
        onMouseLeave={(e) => {
          e.currentTarget.style.background = state.isCollapsed 
            ? 'linear-gradient(135deg, #f8f9fa 0%, #e9ecef 100%)'
            : 'linear-gradient(135deg, #ffffff 0%, #f8f9fa 100%)';
        }}
      >
        {/* Panel Title and Indicator Info */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
          <span>{state.config.title}</span>
          {indicators.length > 0 && (
            <span style={{ 
              fontSize: '0.75rem', 
              color: '#495057',
              background: 'linear-gradient(135deg, #e3f2fd 0%, #bbdefb 100%)',
              padding: '0.25rem 0.6rem',
              borderRadius: '12px',
              fontWeight: '500',
              border: '1px solid #90caf9',
              boxShadow: '0 1px 3px rgba(0, 0, 0, 0.1)'
            }}>
              {indicators.length} indicator{indicators.length > 1 ? 's' : ''}
            </span>
          )}
          {isLoading && (
            <span style={{ fontSize: '0.8rem', color: '#007bff' }}>
              Loading...
            </span>
          )}
          {error && (
            <span style={{ fontSize: '0.8rem', color: '#dc3545' }}>
              Error
            </span>
          )}
        </div>

        {/* Panel Controls */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
          {/* Collapse/Expand Button */}
          {state.config.collapsible && (
            <button
              onClick={(e) => {
                e.stopPropagation();
                handleToggleCollapse();
              }}
              style={{
                background: 'linear-gradient(135deg, #ffffff 0%, #f8f9fa 100%)',
                border: '1px solid #dee2e6',
                cursor: 'pointer',
                fontSize: '0.75rem',
                color: '#495057',
                padding: '0.375rem 0.5rem',
                borderRadius: '6px',
                display: 'flex',
                alignItems: 'center',
                boxShadow: '0 1px 2px rgba(0, 0, 0, 0.05)',
                transition: 'all 0.15s ease',
                fontWeight: '500'
              }}
              title={state.isCollapsed ? 'Expand panel' : 'Collapse panel'}
              onMouseEnter={(e) => {
                e.currentTarget.style.background = 'linear-gradient(135deg, #e9ecef 0%, #dee2e6 100%)';
                e.currentTarget.style.transform = 'translateY(-1px)';
                e.currentTarget.style.boxShadow = '0 2px 4px rgba(0, 0, 0, 0.1)';
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.background = 'linear-gradient(135deg, #ffffff 0%, #f8f9fa 100%)';
                e.currentTarget.style.transform = 'translateY(0)';
                e.currentTarget.style.boxShadow = '0 1px 2px rgba(0, 0, 0, 0.05)';
              }}
            >
              {state.isCollapsed ? '▲' : '▼'}
            </button>
          )}

          {/* Remove Panel Button */}
          <button
            onClick={(e) => {
              e.stopPropagation();
              handleRemove();
            }}
            style={{
              background: 'linear-gradient(135deg, #fff5f5 0%, #fed7d7 100%)',
              border: '1px solid #feb2b2',
              cursor: 'pointer',
              fontSize: '0.75rem',
              color: '#c53030',
              padding: '0.375rem 0.5rem',
              borderRadius: '6px',
              display: 'flex',
              alignItems: 'center',
              boxShadow: '0 1px 2px rgba(0, 0, 0, 0.05)',
              transition: 'all 0.15s ease',
              fontWeight: '500'
            }}
            title="Remove panel"
            onMouseEnter={(e) => {
              e.currentTarget.style.background = 'linear-gradient(135deg, #fed7d7 0%, #fc8181 100%)';
              e.currentTarget.style.transform = 'translateY(-1px)';
              e.currentTarget.style.boxShadow = '0 2px 4px rgba(197, 48, 48, 0.2)';
            }}
            onMouseLeave={(e) => {
              e.currentTarget.style.background = 'linear-gradient(135deg, #fff5f5 0%, #fed7d7 100%)';
              e.currentTarget.style.transform = 'translateY(0)';
              e.currentTarget.style.boxShadow = '0 1px 2px rgba(0, 0, 0, 0.05)';
            }}
          >
            ✕
          </button>
        </div>
      </div>

      {/* Panel Content */}
      {!state.isCollapsed && (
        <div
          style={{
            flex: 1,
            overflow: 'hidden',
            position: 'relative'
          }}
        >
          {/* Error State */}
          {error && (
            <div
              style={{
                position: 'absolute',
                top: 0,
                left: 0,
                right: 0,
                bottom: 0,
                background: 'linear-gradient(135deg, #fff5f5 0%, #fed7d7 100%)',
                border: '1px solid #feb2b2',
                borderRadius: '8px',
                padding: '1.5rem',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                color: '#c53030',
                fontSize: '0.9rem',
                zIndex: 10,
                backdropFilter: 'blur(10px)',
                boxShadow: '0 4px 12px rgba(197, 48, 48, 0.15)'
              }}
            >
              <div style={{ textAlign: 'center' }}>
                <div style={{ 
                  fontWeight: '600', 
                  marginBottom: '0.5rem',
                  fontSize: '1rem',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  gap: '0.5rem'
                }}>
                  <span style={{ fontSize: '1.2rem' }}>⚠️</span>
                  Panel Error
                </div>
                <div style={{ 
                  fontSize: '0.85rem',
                  opacity: 0.9,
                  lineHeight: 1.4
                }}>
                  {error}
                </div>
              </div>
            </div>
          )}

          {/* Loading State */}
          {isLoading && !error && (
            <div
              style={{
                position: 'absolute',
                top: 0,
                left: 0,
                right: 0,
                bottom: 0,
                background: 'linear-gradient(135deg, rgba(255, 255, 255, 0.95) 0%, rgba(248, 249, 250, 0.95) 100%)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                color: '#495057',
                fontSize: '0.9rem',
                zIndex: 10,
                backdropFilter: 'blur(10px)',
                boxShadow: 'inset 0 1px 3px rgba(0, 0, 0, 0.1)'
              }}
            >
              <div style={{ textAlign: 'center' }}>
                <div style={{ 
                  marginBottom: '0.75rem',
                  fontSize: '1.5rem',
                  animation: 'pulse 1.5s ease-in-out infinite'
                }}>
                  ⏳
                </div>
                <div style={{ 
                  fontWeight: '500',
                  fontSize: '0.9rem',
                  color: '#6c757d'
                }}>
                  Loading {state.config.title.toLowerCase()}...
                </div>
                <div style={{
                  width: '40px',
                  height: '3px',
                  background: 'linear-gradient(90deg, #007bff, #6610f2, #007bff)',
                  borderRadius: '2px',
                  margin: '0.75rem auto 0',
                  animation: 'loading-bar 1.5s ease-in-out infinite'
                }}></div>
              </div>
            </div>
          )}

          {/* Chart Content */}
          {!error && !state.isCollapsed && (() => {
            const chartHeight = displayHeight - 40; // Subtract header height
            
            // Only render chart if we have a valid height (minimum 100px)
            if (chartHeight < 100) {
              return null;
            }
            
            return (
              <OscillatorChart
                width={width}
                height={chartHeight}
                oscillatorData={oscillatorData || null}
                isLoading={isLoading}
                error={error || null}
                fuzzyData={fuzzyData}
                fuzzyVisible={fuzzyVisible}
                fuzzyOpacity={fuzzyOpacity}
                fuzzyColorScheme={fuzzyColorScheme}
                onChartCreated={handleChartCreated}
                onChartDestroyed={handleChartDestroyed}
                onCrosshairMove={handleCrosshairMove}
                preserveTimeScale={preserveTimeScale}
                oscillatorConfig={oscillatorConfig}
              />
            );
          })()}
        </div>
      )}
    </div>
  );
};

export default BaseOscillatorPanel;