/**
 * MACDPanel - Specialized panel for MACD indicators
 * 
 * Extends BaseOscillatorPanel with MACD-specific optimizations:
 * - Multi-series rendering (MACD line + Signal line + Histogram)
 * - Dynamic scaling for MACD value ranges
 * - Zero-line reference for divergence analysis
 * - MACD-specific fuzzy overlay with dynamic scaling
 * - Support for multiple MACD instances with different parameters
 */

import { FC, useMemo } from 'react';
import BaseOscillatorPanel from './BaseOscillatorPanel';
import { IPanelComponent } from '../../../types/panels';
import { OscillatorData } from '../charts/OscillatorChart';

/**
 * Props specific to MACDPanel
 */
interface MACDPanelProps extends IPanelComponent {
  /** MACD oscillator data */
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
  onChartCreated?: (chart: any) => void;
  onChartDestroyed?: () => void;
  onCrosshairMove?: (params: any) => void;
  /** Whether to preserve time scale during updates */
  preserveTimeScale?: boolean;
}

/**
 * MACDPanel component with MACD-specific enhancements
 */
const MACDPanel: FC<MACDPanelProps> = (props) => {
  // Calculate dynamic Y-axis range based on MACD data
  const dynamicYAxisRange = useMemo(() => {
    if (!props.oscillatorData || !props.oscillatorData.indicators.length) {
      return undefined;
    }

    // Find MACD-related series (main line, signal, histogram)
    const macdSeries = props.oscillatorData.indicators.filter(series => 
      series.id.includes('macd') || series.id.includes('signal') || series.id.includes('histogram')
    );

    if (macdSeries.length === 0) {
      return undefined;
    }

    // Calculate min/max values across all MACD series
    let minValue = Infinity;
    let maxValue = -Infinity;

    macdSeries.forEach(series => {
      series.data.forEach(point => {
        if (typeof point.value === 'number' && !isNaN(point.value)) {
          minValue = Math.min(minValue, point.value);
          maxValue = Math.max(maxValue, point.value);
        }
      });
    });

    // Add padding for better visualization (10% on each side)
    if (isFinite(minValue) && isFinite(maxValue)) {
      const range = maxValue - minValue;
      const padding = range * 0.1;
      return {
        min: minValue - padding,
        max: maxValue + padding
      };
    }

    return undefined;
  }, [props.oscillatorData]);

  // Generate MACD instances summary for title
  const macdInstanceSummary = useMemo(() => {
    if (props.indicators.length === 0) return '';
    if (props.indicators.length === 1) {
      const params = props.indicators[0].parameters;
      return `(${params.fast_period || 12},${params.slow_period || 26},${params.signal_period || 9})`;
    }
    // For multiple instances, show a summary
    const paramSets = props.indicators.map(ind => {
      const p = ind.parameters;
      return `(${p.fast_period || 12},${p.slow_period || 26},${p.signal_period || 9})`;
    });
    return `${props.indicators.length} instances: ${paramSets.join(', ')}`;
  }, [props.indicators]);

  // MACD-specific configuration enhancements
  const enhancedState = {
    ...props.state,
    config: {
      ...props.state.config,
      title: `MACD Oscillator ${macdInstanceSummary}`,
      yAxisConfig: {
        type: 'auto' as const,
        range: dynamicYAxisRange,
        referenceLines: [
          { value: 0, color: '#6c757d', label: 'Zero Line', style: 'solid' as const }
        ]
      }
    }
  };

  // MACD-specific error handling
  const handleMACDError = (error: string) => {
    // Add MACD-specific error context
    if (error.includes('MACD')) {
      return error;
    }
    
    // Common MACD calculation issues
    if (error.includes('fast_period') || error.includes('slow_period') || error.includes('signal_period')) {
      return `MACD parameter error: ${error}`;
    }
    
    if (error.includes('insufficient data')) {
      return `MACD calculation error: Insufficient data for MACD calculation. Try a longer time period.`;
    }
    
    return `MACD calculation error: ${error}`;
  };

  // Enhanced props with MACD optimizations
  const enhancedProps = {
    ...props,
    state: enhancedState,
    error: props.error ? handleMACDError(props.error) : undefined,
    // MACD benefits from time scale preservation due to convergence/divergence analysis
    preserveTimeScale: props.preserveTimeScale ?? true
  };

  return <BaseOscillatorPanel {...enhancedProps} />;
};

export default MACDPanel;