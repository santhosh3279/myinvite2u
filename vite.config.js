import { fileURLToPath } from 'node:url'
import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import frappeui from 'frappe-ui/vite'

const resolve = (path) => fileURLToPath(new URL(path, import.meta.url))

export default defineConfig({
  root: resolve('./frontend'),
  server: {
    host: '0.0.0.0',
    watch: {
      // Bench can exhaust Linux's inotify watchers; polling keeps HMR working.
      usePolling: true,
      interval: 300,
    },
  },
  plugins: [
    frappeui({
      jinjaBootData: false,
      buildConfig: {
        outDir: resolve('./invite/public/frontend'),
        indexHtmlPath: resolve('./invite/www/invite.html'),
        baseUrl: '/assets/invite/frontend/',
      },
    }),
    vue(),
  ],
})
