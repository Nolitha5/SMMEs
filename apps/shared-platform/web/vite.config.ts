import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const HERE = path.dirname(fileURLToPath(import.meta.url));

export default defineConfig({
  root: HERE,
  envDir: path.resolve(HERE, '..'),
  plugins: [react()],
  server: {
    port: 5174,
    strictPort: true,
    proxy: {
      '/api': { target: 'http://localhost:8790', changeOrigin: true }
    }
  },
  build: {
    outDir: path.resolve(HERE, '../dist/web'),
    emptyOutDir: true
  }
});
