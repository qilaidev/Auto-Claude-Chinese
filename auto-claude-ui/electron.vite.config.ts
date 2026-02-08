import { defineConfig, externalizeDepsPlugin } from 'electron-vite';
import react from '@vitejs/plugin-react';
import { resolve } from 'path';

export default defineConfig({
  main: {
    plugins: [externalizeDepsPlugin({
      // 打包时需要内联的依赖（不会出现在打包后的 node_modules 中）
      // IMPORTANT: 如果主进程 import 了某个包且打包后报 "Cannot find module" 错误，
      // 需要将该包添加到此 exclude 列表中
      // 参考: src/main/app-updater.ts (electron-updater), src/main/app-logger.ts (electron-log)
      exclude: [
        'uuid',
        'chokidar',
        'ioredis',
        'electron-updater',  // 用于自动更新 (app-updater.ts)
        'electron-log',      // 用于日志记录 (app-logger.ts)
        '@electron-toolkit/utils'
      ]
    })],
    build: {
      rollupOptions: {
        input: {
          index: resolve(__dirname, 'src/main/index.ts')
        },
        // 原生模块必须外部化，由 electron-builder 重新编译
        // 同时需要在 package.json extraResources 中配置复制规则
        external: ['@lydell/node-pty']
      }
    }
  },
  preload: {
    plugins: [externalizeDepsPlugin()],
    build: {
      rollupOptions: {
        input: {
          index: resolve(__dirname, 'src/preload/index.ts')
        }
      }
    }
  },
  renderer: {
    root: resolve(__dirname, 'src/renderer'),
    build: {
      rollupOptions: {
        input: {
          index: resolve(__dirname, 'src/renderer/index.html')
        }
      }
    },
    plugins: [react()],
    resolve: {
      alias: {
        '@': resolve(__dirname, 'src/renderer'),
        '@shared': resolve(__dirname, 'src/shared')
      }
    },
    server: {
      watch: {
        // Ignore directories to prevent HMR conflicts during merge operations
        // Using absolute paths and broader patterns
        ignored: [
          '**/node_modules/**',
          '**/.git/**',
          '**/.worktrees/**',
          '**/.auto-claude/**',
          '**/out/**',
          // Ignore the parent autonomous-coding directory's worktrees
          resolve(__dirname, '../.worktrees/**'),
          resolve(__dirname, '../.auto-claude/**'),
        ]
      }
    }
  }
});
