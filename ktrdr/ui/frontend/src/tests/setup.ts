import '@testing-library/jest-dom';

// Mock any global objects or browser APIs here if needed
// This file runs before each test

// Suppress React 19 console warnings during tests
const originalConsoleError = console.error;
console.error = (...args: any[]) => {
  // Filter out React 19 specific warnings that aren't relevant to tests
  if (
    typeof args[0] === 'string' &&
    (args[0].includes('ReactDOM.render is no longer supported') ||
      args[0].includes('Warning: ReactDOM.render'))
  ) {
    return;
  }
  originalConsoleError(...args);
};