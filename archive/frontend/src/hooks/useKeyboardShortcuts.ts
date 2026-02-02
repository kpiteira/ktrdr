import { useEffect, useCallback } from 'react';

/**
 * Keyboard shortcuts hook for common actions
 * 
 * Provides keyboard shortcuts for frequently used actions to improve
 * user productivity and accessibility.
 */

export interface KeyboardShortcut {
  key: string;
  ctrlKey?: boolean;
  shiftKey?: boolean;
  altKey?: boolean;
  metaKey?: boolean;
  action: () => void;
  description: string;
  category?: string;
}

interface UseKeyboardShortcutsProps {
  shortcuts: KeyboardShortcut[];
  enabled?: boolean;
}

export const useKeyboardShortcuts = ({ shortcuts, enabled = true }: UseKeyboardShortcutsProps) => {
  const handleKeyDown = useCallback((event: KeyboardEvent) => {
    if (!enabled) return;
    
    // Don't trigger shortcuts when user is typing in input fields
    const target = event.target as HTMLElement;
    if (target.tagName === 'INPUT' || target.tagName === 'TEXTAREA' || target.isContentEditable) {
      return;
    }

    const matchingShortcut = shortcuts.find(shortcut => {
      return (
        shortcut.key.toLowerCase() === event.key.toLowerCase() &&
        !!shortcut.ctrlKey === event.ctrlKey &&
        !!shortcut.shiftKey === event.shiftKey &&
        !!shortcut.altKey === event.altKey &&
        !!shortcut.metaKey === event.metaKey
      );
    });

    if (matchingShortcut) {
      event.preventDefault();
      event.stopPropagation();
      matchingShortcut.action();
    }
  }, [shortcuts, enabled]);

  useEffect(() => {
    if (enabled) {
      document.addEventListener('keydown', handleKeyDown);
      return () => document.removeEventListener('keydown', handleKeyDown);
    }
  }, [handleKeyDown, enabled]);

  return { shortcuts };
};

// Helper function to format shortcut display
export const formatShortcut = (shortcut: KeyboardShortcut): string => {
  const parts: string[] = [];
  
  if (shortcut.ctrlKey) parts.push(isMac ? '⌃' : 'Ctrl');
  if (shortcut.shiftKey) parts.push(isMac ? '⇧' : 'Shift');
  if (shortcut.altKey) parts.push(isMac ? '⌥' : 'Alt');
  if (shortcut.metaKey) parts.push(isMac ? '⌘' : 'Meta');
  parts.push(shortcut.key.toUpperCase());
  
  return parts.join(' + ');
};

// Detect if user is on Mac
const isMac = typeof navigator !== 'undefined' && navigator.platform.toUpperCase().indexOf('MAC') >= 0;

// Common shortcut presets
export const createCommonShortcuts = (actions: {
  toggleLeftSidebar?: () => void;
  toggleRightSidebar?: () => void;
  addSMA?: () => void;
  addRSI?: () => void;
  clearIndicators?: () => void;
  showHelp?: () => void;
  focusSymbolSelector?: () => void;
}) => {
  const shortcuts: KeyboardShortcut[] = [];
  
  // Use Cmd on Mac, Ctrl on other platforms
  const modifierKey = isMac;

  if (actions.toggleLeftSidebar) {
    shortcuts.push({
      key: '1',
      [isMac ? 'metaKey' : 'ctrlKey']: true,
      action: actions.toggleLeftSidebar,
      description: 'Toggle left sidebar',
      category: 'Navigation'
    });
  }

  if (actions.toggleRightSidebar) {
    shortcuts.push({
      key: '2',
      [isMac ? 'metaKey' : 'ctrlKey']: true,
      action: actions.toggleRightSidebar,
      description: 'Toggle right sidebar',
      category: 'Navigation'
    });
  }


  if (actions.clearIndicators) {
    shortcuts.push({
      key: 'Backspace',
      [isMac ? 'metaKey' : 'ctrlKey']: true,
      shiftKey: true,
      action: actions.clearIndicators,
      description: 'Clear all indicators',
      category: 'Indicators'
    });
  }

  if (actions.showHelp) {
    shortcuts.push({
      key: 'h',
      [isMac ? 'metaKey' : 'ctrlKey']: true,
      action: actions.showHelp,
      description: 'Show keyboard shortcuts',
      category: 'Help'
    });
  }

  if (actions.focusSymbolSelector) {
    shortcuts.push({
      key: 'k',
      [isMac ? 'metaKey' : 'ctrlKey']: true,
      action: actions.focusSymbolSelector,
      description: 'Focus symbol selector',
      category: 'Navigation'
    });
  }

  // General shortcuts
  shortcuts.push({
    key: 'Escape',
    action: () => {
      // Clear focus from any active element
      const activeElement = document.activeElement as HTMLElement;
      if (activeElement && activeElement.blur) {
        activeElement.blur();
      }
    },
    description: 'Clear focus/cancel',
    category: 'General'
  });

  return shortcuts;
};