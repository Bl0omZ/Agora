import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    warmup: {
      clientFiles: ['./src/main.tsx', './src/App.tsx'],
    },
    proxy: {
      '/ws': {
        target: 'http://localhost:8001',
        ws: true,
        configure: (proxy) => {
          proxy.on('error', () => {});
        },
      },
      '/api': {
        target: 'http://localhost:8001',
        configure: (proxy) => {
          proxy.on('error', () => {});
        },
      },
    },
  },
  build: {
    outDir: 'dist',
    emptyOutDir: true,
  },
});
