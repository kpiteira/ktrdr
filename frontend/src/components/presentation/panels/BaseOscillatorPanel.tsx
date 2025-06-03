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
        borderRadius: '4px',
        overflow: 'hidden',
        transition: 'height 0.3s ease-in-out',
        display: 'flex',
        flexDirection: 'column'
      }}
      data-panel-id={state.id}
      data-panel-type={state.config.type}
    >
      {/* Panel Header */}
      <div
        style={{
          height: '40px',
          backgroundColor: '#f8f9fa',
          borderBottom: state.isCollapsed ? 'none' : '1px solid #e0e0e0',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          padding: '0 0.75rem',
          fontSize: '0.9rem',
          fontWeight: '500',
          color: '#333',
          flexShrink: 0
        }}
      >
        {/* Panel Title and Indicator Info */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
          <span>{state.config.title}</span>
          {indicators.length > 0 && (
            <span style={{ 
              fontSize: '0.8rem', 
              color: '#666',
              backgroundColor: '#e9ecef',
              padding: '0.2rem 0.4rem',
              borderRadius: '3px'
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
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.25rem' }}>
          {/* Collapse/Expand Button */}
          {state.config.collapsible && (
            <button
              onClick={handleToggleCollapse}
              style={{
                background: 'none',
                border: 'none',
                cursor: 'pointer',
                fontSize: '0.8rem',
                color: '#666',
                padding: '0.25rem',
                borderRadius: '3px',
                display: 'flex',
                alignItems: 'center'
              }}
              title={state.isCollapsed ? 'Expand panel' : 'Collapse panel'}
            >
              {state.isCollapsed ? '▲' : '▼'}
            </button>
          )}

          {/* Remove Panel Button */}
          <button
            onClick={handleRemove}
            style={{
              background: 'none',
              border: 'none',
              cursor: 'pointer',
              fontSize: '0.8rem',
              color: '#dc3545',
              padding: '0.25rem',
              borderRadius: '3px'
            }}
            title="Remove panel"
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
                backgroundColor: '#fff3cd',
                border: '1px solid #ffeaa7',
                borderRadius: '4px',
                padding: '1rem',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                color: '#856404',
                fontSize: '0.9rem',
                zIndex: 10
              }}
            >
              <div style={{ textAlign: 'center' }}>
                <div style={{ fontWeight: '500', marginBottom: '0.5rem' }}>
                  Panel Error
                </div>
                <div>{error}</div>
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
                backgroundColor: 'rgba(255, 255, 255, 0.8)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                color: '#666',
                fontSize: '0.9rem',
                zIndex: 10
              }}
            >
              <div style={{ textAlign: 'center' }}>
                <div style={{ marginBottom: '0.5rem' }}>⏳</div>
                <div>Loading {state.config.title.toLowerCase()}...</div>
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