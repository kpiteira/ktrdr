/**
 * Common types for UI components
 */

export type ThemeMode = 'light' | 'dark';

export interface ThemeContextType {
  theme: ThemeMode;
  toggleTheme: () => void;
}

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