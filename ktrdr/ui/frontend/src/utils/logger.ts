// Simple frontend logger using console only
// Browser console.log does NOT appear in Docker logs

export const createComponentLogger = (component: string) => {
  const timestamp = () => new Date().toISOString();
  
  return {
    info: (message: string, data?: any) => {
      const logMessage = `[${timestamp()}] [INFO] [${component}] ${message}`;
      if (data) {
        console.log(logMessage, data);
      } else {
        console.log(logMessage);
      }
    },
    warn: (message: string, data?: any) => {
      const logMessage = `[${timestamp()}] [WARN] [${component}] ${message}`;
      if (data) {
        console.warn(logMessage, data);
      } else {
        console.warn(logMessage);
      }
    },
    error: (message: string, data?: any) => {
      const logMessage = `[${timestamp()}] [ERROR] [${component}] ${message}`;
      if (data) {
        console.error(logMessage, data);
      } else {
        console.error(logMessage);
      }
    },
    debug: (message: string, data?: any) => {
      const logMessage = `[${timestamp()}] [DEBUG] [${component}] ${message}`;
      if (data) {
        console.debug(logMessage, data);
      } else {
        console.debug(logMessage);
      }
    }
  };
};