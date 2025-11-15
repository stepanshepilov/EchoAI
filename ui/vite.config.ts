// vite.config.ts
import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      // Это правило теперь должно обрабатывать и HTTP, и WebSocket
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
        ws: true, // Включаем WebSocket
      },
    },
  },
});