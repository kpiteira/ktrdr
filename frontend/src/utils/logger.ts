/**
 * Frontend logging utility with structured log levels
 * Works with vite-plugin-terminal to forward browser logs to Docker
 */

//import terminal from 'virtual:terminal'

export enum LogLevel {
  DEBUG = 0,
  INFO = 1,
  WARN = 2,
  ERROR = 3,
  NONE = 4
}
const terminal = (import.meta as any).env?.VITE_TERMINAL || console;

interface LoggerConfig {
  level: LogLevel;
  prefix?: string;
  enableTimestamp?: boolean;
}

class Logger {
  private level: LogLevel;
  private prefix: string;
  private enableTimestamp: boolean;

  constructor(config: LoggerConfig) {
    this.level = config.level || LogLevel.INFO;
    this.prefix = config.prefix || '';
    this.enableTimestamp = config.enableTimestamp ?? true;
  }

  private shouldLog(level: LogLevel): boolean {
    return level >= this.level;
  }

  private formatMessage(level: string, message: string, ...args: any[]): string {
    const parts = [];
    
    if (this.enableTimestamp) {
      parts.push(`[${new Date().toISOString()}]`);
    }
    
    parts.push(`[${level}]`);
    
    if (this.prefix) {
      parts.push(`[${this.prefix}]`);
    }
    
    parts.push(message);
    
    return parts.join(' ');
  }

  debug(message: string, ...args: any[]): void {
    if (this.shouldLog(LogLevel.DEBUG)) {
      console.log(this.formatMessage('DEBUG', message), ...args);
      terminal.log(this.formatMessage('DEBUG', message), ...args);
    }
  }

  info(message: string, ...args: any[]): void {
    if (this.shouldLog(LogLevel.INFO)) {
      console.info(this.formatMessage('INFO', message), ...args);
      terminal.info(this.formatMessage('INFO', message), ...args);
    }
  }

  warn(message: string, ...args: any[]): void {
    if (this.shouldLog(LogLevel.WARN)) {
      console.warn(this.formatMessage('WARN', message), ...args);
      terminal.warn(this.formatMessage('WARN', message), ...args);
    }
  }

  error(message: string, error?: Error | unknown, ...args: any[]): void {
    if (this.shouldLog(LogLevel.ERROR)) {
      const errorMessage = this.formatMessage('ERROR', message);
      
      if (error instanceof Error) {
        console.error(errorMessage, '\n', error.stack || error.message, ...args);
        terminal.error(errorMessage, '\n', error.stack || error.message, ...args);
      } else if (error) {
        console.error(errorMessage, error, ...args);
        terminal.error(errorMessage, error, ...args);
      } else {
        console.error(errorMessage, ...args);
        terminal.error(errorMessage, ...args);
      }
    }
  }

  /**
   * Create a child logger with a specific prefix
   */
  child(prefix: string): Logger {
    const childPrefix = this.prefix ? `${this.prefix}:${prefix}` : prefix;
    return new Logger({
      level: this.level,
      prefix: childPrefix,
      enableTimestamp: this.enableTimestamp
    });
  }

  /**
   * Set the log level dynamically
   */
  setLevel(level: LogLevel): void {
    this.level = level;
  }
}

// Get log level from environment or default to INFO
function getDefaultLogLevel(): LogLevel {
  const envLevel = import.meta.env.VITE_LOG_LEVEL?.toUpperCase();
  
  switch (envLevel) {
    case 'DEBUG':
      return LogLevel.DEBUG;
    case 'INFO':
      return LogLevel.INFO;
    case 'WARN':
      return LogLevel.WARN;
    case 'ERROR':
      return LogLevel.ERROR;
    case 'NONE':
      return LogLevel.NONE;
    default:
      // In development, default to DEBUG; in production, default to INFO
      return import.meta.env.DEV ? LogLevel.DEBUG : LogLevel.INFO;
  }
}

// Create the root logger instance
const rootLogger = new Logger({
  level: getDefaultLogLevel(),
  enableTimestamp: true
});

// Export factory function to create component-specific loggers
export function createLogger(prefix: string): Logger {
  return rootLogger.child(prefix);
}

// Export root logger for global use
export const logger = rootLogger;

// Export LogLevel for configuration
export { LogLevel as LOG_LEVEL };

// Development helpers
if (import.meta.env.DEV) {
  // Expose logger to window for debugging
  (window as any).__logger = rootLogger;
  (window as any).__LogLevel = LogLevel;
  
  console.info('[Logger] Initialized with level:', LogLevel[rootLogger['level']]);
  console.info('[Logger] Available in window.__logger for debugging');
}