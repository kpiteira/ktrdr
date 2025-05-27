import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import path from 'path';

// Custom Vite plugin for frontend logging
const frontendLoggerPlugin = () => {
  return {
    name: 'frontend-logger',
    configureServer(server) {
      server.middlewares.use('/debug/frontend-log', (req, res, next) => {
        if (req.method === 'POST') {
          let body = '';
          req.on('data', chunk => {
            body += chunk.toString();
          });
          req.on('end', () => {
            try {
              const logData = JSON.parse(body);
              const timestamp = new Date().toISOString();
              const logMessage = `[${timestamp}] [FRONTEND-${logData.component}] ${logData.message}`;
              
              // Log to Vite dev server console (appears in Docker logs)
              if (logData.level === 'ERROR') {
                console.error(logMessage, logData.data ? `| Data: ${logData.data}` : '');
              } else if (logData.level === 'WARN') {
                console.warn(logMessage, logData.data ? `| Data: ${logData.data}` : '');
              } else {
                console.log(logMessage, logData.data ? `| Data: ${logData.data}` : '');
              }
              
              res.writeHead(200, { 'Content-Type': 'application/json' });
              res.end(JSON.stringify({ success: true }));
            } catch (error) {
              console.error('Error processing frontend log:', error);
              res.writeHead(400, { 'Content-Type': 'application/json' });
              res.end(JSON.stringify({ error: 'Invalid JSON' }));
            }
          });
        } else {
          next();
        }
      });
    }
  };
};

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [react(), frontendLoggerPlugin()],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
  server: {
    port: 5173,
    host: '0.0.0.0', // Allow connections from other devices, useful for Docker
    watch: {
      usePolling: true, // Needed for Docker on some systems
    },
    // Add proxy configuration to redirect API requests to the backend container
    proxy: {
      '/api': {
        target: 'http://backend:8000',
        changeOrigin: true,
        secure: false,
      }
    }
  },
});
