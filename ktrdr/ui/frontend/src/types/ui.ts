/**
 * UI types for KTRDR frontend
 * Defines types for UI components and theme settings
 */

// Theme mode type
export type ThemeMode = 'light' | 'dark';

export interface ThemeContextType {
  theme: ThemeMode;
  toggleTheme: () => void;
}

// Chart settings type
export interface ChartSettings {
  height: number;
  showVolume: boolean;
  showGridlines: boolean;
  crosshair: boolean;
  priceScale: 'right' | 'left' | 'both';
}

// View types
export type ViewMode = 'dashboard' | 'chart' | 'scanner' | 'strategy' | 'settings';

export type ButtonVariant = 'primary' | 'secondary' | 'danger' | 'outline' | 'ghost';
export type ButtonSize = 'small' | 'medium' | 'large';

export type InputType = 'text' | 'number' | 'email' | 'password' | 'date';

export interface SelectOption {
  value: string;
  label: string;
}

export interface TabItem {
  key: string;
  label: string;
  content: React.ReactNode;
}