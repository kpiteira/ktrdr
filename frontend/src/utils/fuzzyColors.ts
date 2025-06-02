/**
 * Fuzzy Color Utility System
 * 
 * Provides color schemes and utilities for fuzzy membership visualization.
 * Supports different color schemes and opacity calculations for fuzzy overlays.
 */

export interface FuzzyColorScheme {
  low: string;
  neutral: string;
  high: string;
  [key: string]: string; // Allow additional fuzzy sets
}

export interface ColorSchemes {
  default: FuzzyColorScheme;
  monochrome: FuzzyColorScheme;
  trading: FuzzyColorScheme;
  [key: string]: FuzzyColorScheme;
}

/**
 * Predefined fuzzy color schemes
 */
export const FUZZY_COLOR_SCHEMES: ColorSchemes = {
  default: {
    low: '#2196F3',      // Blue for low values
    neutral: '#9E9E9E',  // Gray for neutral/medium values
    high: '#F44336',     // Red for high values
    negative: '#F44336', // Red for negative (MACD)
    positive: '#4CAF50', // Green for positive (MACD)
    below: '#2196F3',    // Blue for below (EMA)
    above: '#4CAF50'     // Green for above (EMA)
  },
  monochrome: {
    low: '#424242',      // Dark gray for low
    neutral: '#757575',  // Medium gray for neutral
    high: '#212121',     // Very dark gray for high
    negative: '#616161', // Medium-dark gray for negative
    positive: '#424242', // Dark gray for positive
    below: '#757575',    // Medium gray for below
    above: '#424242'     // Dark gray for above
  },
  trading: {
    low: '#4CAF50',      // Green for low (bullish for RSI)
    neutral: '#FF9800',  // Orange for neutral
    high: '#F44336',     // Red for high (bearish for RSI)
    negative: '#F44336', // Red for negative (bearish)
    positive: '#4CAF50', // Green for positive (bullish)
    below: '#F44336',    // Red for below
    above: '#4CAF50'     // Green for above
  }
};

/**
 * Get color for a specific fuzzy set from a color scheme
 */
export const getFuzzyColor = (
  setName: string, 
  scheme: string = 'default'
): string => {
  const colorScheme = FUZZY_COLOR_SCHEMES[scheme] || FUZZY_COLOR_SCHEMES.default;
  return colorScheme[setName] || colorScheme.neutral || '#9E9E9E';
};

/**
 * Convert hex color to RGBA with specified opacity
 */
export const hexToRgba = (hex: string, opacity: number): string => {
  // Remove # if present
  const cleanHex = hex.replace('#', '');
  
  // Parse RGB values
  const r = parseInt(cleanHex.substr(0, 2), 16);
  const g = parseInt(cleanHex.substr(2, 2), 16);
  const b = parseInt(cleanHex.substr(4, 2), 16);
  
  // Clamp opacity to valid range
  const clampedOpacity = Math.max(0, Math.min(1, opacity));
  
  return `rgba(${r}, ${g}, ${b}, ${clampedOpacity})`;
};

/**
 * Calculate opacity based on membership strength
 * Higher membership values get higher opacity (more visible)
 */
export const calculateMembershipOpacity = (
  membershipValue: number,
  baseOpacity: number = 0.3,
  minOpacity: number = 0.05
): number => {
  // Clamp membership value to valid range
  const clampedMembership = Math.max(0, Math.min(1, membershipValue));
  
  // Calculate opacity: minOpacity when membership=0, baseOpacity when membership=1
  const opacity = minOpacity + (baseOpacity - minOpacity) * clampedMembership;
  
  return Math.max(0, Math.min(1, opacity));
};

/**
 * Detect if the current theme is dark mode
 * This is a simple implementation - can be enhanced with theme context
 */
export const isDarkTheme = (): boolean => {
  // Check for dark mode using CSS media query
  if (typeof window !== 'undefined' && window.matchMedia) {
    return window.matchMedia('(prefers-color-scheme: dark)').matches;
  }
  return false;
};

/**
 * Adjust color brightness for better contrast in different themes
 */
export const adjustColorForTheme = (color: string, isDark: boolean = isDarkTheme()): string => {
  if (isDark) {
    // In dark theme, make colors slightly brighter
    return lightenColor(color, 0.2);
  } else {
    // In light theme, keep colors as-is or slightly darker
    return darkenColor(color, 0.1);
  }
};

/**
 * Lighten a hex color by a percentage
 */
export const lightenColor = (hex: string, percent: number): string => {
  const cleanHex = hex.replace('#', '');
  const num = parseInt(cleanHex, 16);
  const r = Math.min(255, Math.floor((num >> 16) + (255 - (num >> 16)) * percent));
  const g = Math.min(255, Math.floor(((num >> 8) & 0x00FF) + (255 - ((num >> 8) & 0x00FF)) * percent));
  const b = Math.min(255, Math.floor((num & 0x0000FF) + (255 - (num & 0x0000FF)) * percent));
  
  return `#${((r << 16) | (g << 8) | b).toString(16).padStart(6, '0')}`;
};

/**
 * Darken a hex color by a percentage
 */
export const darkenColor = (hex: string, percent: number): string => {
  const cleanHex = hex.replace('#', '');
  const num = parseInt(cleanHex, 16);
  const r = Math.max(0, Math.floor((num >> 16) * (1 - percent)));
  const g = Math.max(0, Math.floor(((num >> 8) & 0x00FF) * (1 - percent)));
  const b = Math.max(0, Math.floor((num & 0x0000FF) * (1 - percent)));
  
  return `#${((r << 16) | (g << 8) | b).toString(16).padStart(6, '0')}`;
};

/**
 * Check if a color has sufficient contrast for accessibility
 * Based on WCAG guidelines
 */
export const hasGoodContrast = (
  foreground: string, 
  background: string = '#FFFFFF'
): boolean => {
  const getLuminance = (hex: string): number => {
    const cleanHex = hex.replace('#', '');
    const r = parseInt(cleanHex.substr(0, 2), 16) / 255;
    const g = parseInt(cleanHex.substr(2, 2), 16) / 255;
    const b = parseInt(cleanHex.substr(4, 2), 16) / 255;
    
    const toLinear = (c: number) => c <= 0.03928 ? c / 12.92 : Math.pow((c + 0.055) / 1.055, 2.4);
    
    return 0.2126 * toLinear(r) + 0.7152 * toLinear(g) + 0.0722 * toLinear(b);
  };
  
  const l1 = getLuminance(foreground);
  const l2 = getLuminance(background);
  const contrast = (Math.max(l1, l2) + 0.05) / (Math.min(l1, l2) + 0.05);
  
  return contrast >= 4.5; // WCAG AA standard
};

/**
 * Get accessible color for fuzzy overlays
 * Automatically adjusts colors for better accessibility
 */
export const getAccessibleFuzzyColor = (
  setName: string,
  scheme: string = 'default',
  backgroundColor: string = '#FFFFFF'
): string => {
  let color = getFuzzyColor(setName, scheme);
  
  // If contrast is poor, adjust the color
  if (!hasGoodContrast(color, backgroundColor)) {
    const isDark = isDarkTheme();
    color = isDark ? lightenColor(color, 0.3) : darkenColor(color, 0.3);
  }
  
  return color;
};

/**
 * Create a complete color configuration for a fuzzy indicator
 * Returns colors with proper opacity and theme adjustments
 */
export interface FuzzyColorConfig {
  setName: string;
  baseColor: string;
  fillColor: string;
  borderColor: string;
}

export const createFuzzyColorConfig = (
  setName: string,
  scheme: string = 'default',
  opacity: number = 0.3
): FuzzyColorConfig => {
  const baseColor = getAccessibleFuzzyColor(setName, scheme);
  const fillColor = hexToRgba(baseColor, opacity);
  const borderColor = hexToRgba(baseColor, Math.min(1, opacity + 0.2)); // Slightly more opaque border
  
  return {
    setName,
    baseColor,
    fillColor,
    borderColor
  };
};