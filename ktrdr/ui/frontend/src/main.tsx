import React from 'react';
import ReactDOM from 'react-dom/client';
import App from './App';
import './index.css';

// Test if console logs appear in Docker logs
console.log('=== FRONTEND LOGGING TEST ===');
console.log('main.tsx loaded at:', new Date().toISOString());
console.log('Environment:', import.meta.env.MODE);
console.log('=== END TEST ===');

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
);