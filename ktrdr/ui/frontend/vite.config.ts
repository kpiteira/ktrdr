import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import Terminal from 'vite-plugin-terminal';
import path from 'path';

// https://vitejs.dev/config/
export default defineConfig(({ command, mode }) => {
  console.log('🚀 VITE COMMAND:', command); // 'serve' or 'build'
  console.log('🚀 VITE MODE:', mode);       // 'development', 'production', etc.

  return {
    plugins: [
      react(),
      Terminal({
        console: 'terminal',
        output: ['terminal', 'console'],
      })
    ],
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
  };
});
