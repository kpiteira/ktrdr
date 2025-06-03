/**
 * RSIPanel - Specialized panel for RSI indicators
 * 
 * Extends BaseOscillatorPanel with RSI-specific optimizations:
 * - Fixed 0-100 scaling with overbought/oversold reference lines
 * - RSI-specific fuzzy overlay with fixed scaling
 * - Support for multiple RSI instances with different periods
 * - RSI-specific error handling and edge cases
 */

import { FC } from 'react';
import BaseOscillatorPanel from './BaseOscillatorPanel';
import { IPanelComponent } from '../../../types/panels';
import { OscillatorData } from '../charts/OscillatorChart';

/**
 * Props specific to RSIPanel
 */
interface RSIPanelProps extends IPanelComponent {
  /** RSI oscillator data */
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
 * RSIPanel component with RSI-specific enhancements
 */
const RSIPanel: FC<RSIPanelProps> = (props) => {
  // Generate RSI instances summary for title
  const rsiInstanceSummary = (() => {
    if (props.indicators.length === 0) return '';
    if (props.indicators.length === 1) {
      const period = props.indicators[0].parameters.period || 14;
      return `(${period})`;
    }
    // For multiple instances, show periods
    const periods = props.indicators.map(ind => ind.parameters.period || 14);
    return `${props.indicators.length} instances: (${periods.join(', ')})`;
  })();

  // RSI-specific configuration enhancements
  const enhancedState = {
    ...props.state,
    config: {
      ...props.state.config,
      title: `RSI Oscillator ${rsiInstanceSummary}`,
      yAxisConfig: {
        type: 'fixed' as const,
        range: { min: 0, max: 100 },
        referenceLines: [
          { value: 30, color: '#dc3545', label: 'Oversold (30)', style: 'dashed' as const },
          { value: 50, color: '#6c757d', label: 'Neutral (50)', style: 'dotted' as const },
          { value: 70, color: '#28a745', label: 'Overbought (70)', style: 'dashed' as const }
        ]
      }
    }
  };

  // RSI-specific error handling
  const handleRSIError = (error: string) => {
    // Add RSI-specific error context
    const rsiError = error.includes('RSI') ? error : `RSI calculation error: ${error}`;
    return rsiError;
  };

  // Enhanced props with RSI optimizations
  const enhancedProps = {
    ...props,
    state: enhancedState,
    error: props.error ? handleRSIError(props.error) : undefined,
    // RSI uses fixed scaling for fuzzy overlays (0-100 range)
    preserveTimeScale: props.preserveTimeScale ?? true
  };

  return <BaseOscillatorPanel {...enhancedProps} />;
};

export default RSIPanel;