/**
 * Type definitions for the multi-panel oscillator architecture
 */

import { IndicatorInfo } from '../store/indicatorRegistry';
import { IChartApi } from 'lightweight-charts';

/**
 * Panel configuration interface - defines what type of oscillator panel this is
 */
export interface PanelConfig {
  /** Panel type identifier (rsi, macd, stochastic, etc.) */
  type: string;
  /** Display name for the panel */
  title: string;
  /** Default height in pixels */
  defaultHeight: number;
  /** Whether the panel can be collapsed */
  collapsible: boolean;
  /** Y-axis configuration */
  yAxisConfig: {
    /** Fixed range (e.g., RSI 0-100) or auto-scale */
    type: 'fixed' | 'auto';
    /** For fixed range panels */
    range?: { min: number; max: number };
    /** Reference lines to display */
    referenceLines?: Array<{
      value: number;
      color: string;
      label?: string;
      style?: 'solid' | 'dashed' | 'dotted';
    }>;
  };
}

/**
 * Panel state interface - tracks the current state of a panel instance
 */
export interface PanelState {
  /** Unique panel instance ID */
  id: string;
  /** Panel configuration */
  config: PanelConfig;
  /** Current height in pixels */
  height: number;
  /** Whether the panel is collapsed */
  isCollapsed: boolean;
  /** Whether the panel is visible */
  isVisible: boolean;
  /** Panel order in the layout */
  order: number;
  /** Error state */
  error?: string;
  /** Loading state */
  isLoading: boolean;
}

/**
 * Panel lifecycle events interface
 */
export interface PanelLifecycle {
  /** Called when panel is created */
  onCreate?: (panelId: string) => void;
  /** Called when panel is destroyed */
  onDestroy?: (panelId: string) => void;
  /** Called when panel configuration changes */
  onConfigChange?: (panelId: string, config: PanelConfig) => void;
  /** Called when panel state changes */
  onStateChange?: (panelId: string, state: PanelState) => void;
  /** Called when chart is ready */
  onChartReady?: (panelId: string, chart: IChartApi) => void;
}

/**
 * Panel component interface - standardizes panel component behavior
 */
export interface IPanelComponent {
  /** Panel state */
  state: PanelState;
  /** Indicators associated with this panel */
  indicators: IndicatorInfo[];
  /** Panel lifecycle callbacks */
  lifecycle: PanelLifecycle;
  /** Chart dimensions */
  width: number;
  height: number;
  /** Panel actions */
  actions: {
    /** Toggle panel collapse state */
    toggleCollapse: () => void;
    /** Update panel height */
    updateHeight: (height: number) => void;
    /** Remove the panel */
    remove: () => void;
    /** Update panel configuration */
    updateConfig: (config: Partial<PanelConfig>) => void;
  };
}

/**
 * Panel manager interface - manages multiple panel instances
 */
export interface IPanelManager {
  /** All panel states */
  panels: PanelState[];
  /** Create a new panel */
  createPanel: (type: string, indicators: IndicatorInfo[]) => string;
  /** Remove a panel */
  removePanel: (panelId: string) => void;
  /** Update panel state */
  updatePanelState: (panelId: string, updates: Partial<PanelState>) => void;
  /** Reorder panels */
  reorderPanels: (panelIds: string[]) => void;
  /** Get panel by ID */
  getPanel: (panelId: string) => PanelState | undefined;
  /** Get panels by type */
  getPanelsByType: (type: string) => PanelState[];
}

/**
 * Panel registry - defines available panel types and their configurations
 */
export interface PanelRegistryEntry {
  /** Panel type identifier */
  type: string;
  /** Default panel configuration */
  defaultConfig: PanelConfig;
  /** Supported indicator types for this panel */
  supportedIndicators: string[];
  /** Component factory function */
  createComponent: (props: IPanelComponent) => React.ComponentType<IPanelComponent>;
}

/**
 * Panel synchronization interface - coordinates multiple panels
 */
export interface IPanelSynchronizer {
  /** Register a chart for synchronization */
  registerChart: (panelId: string, chart: IChartApi) => void;
  /** Unregister a chart */
  unregisterChart: (panelId: string) => void;
  /** Synchronize crosshair across all panels */
  synchronizeCrosshair: (sourcePanelId: string, params: any) => void;
  /** Synchronize time scale across all panels */
  synchronizeTimeScale: (sourcePanelId: string, range: any) => void;
}