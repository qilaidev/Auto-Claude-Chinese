/**
 * Configuration for Auto Claude updater
 */

/**
 * GitHub repository configuration
 */
export const GITHUB_CONFIG = {
  owner: 'tytsxai',
  repo: 'Auto-Claude-Chinese',
  autoBuildPath: 'auto-claude', // Path within repo where auto-claude lives
  /**
   * Optional GitHub proxy for users无法直连 GitHub 时使用
   * Set AUTO_CLAUDE_GITHUB_PROXY to a proxy prefix like https://mirror.ghproxy.com
   */
  proxyBase: process.env.AUTO_CLAUDE_GITHUB_PROXY?.replace(/\/+$/, '')
} as const;

/**
 * Whether to attempt a built-in GitHub proxy fallback when the direct request fails
 * Disable by setting AUTO_CLAUDE_DISABLE_PROXY_FALLBACK=true
 */
export const ENABLE_PROXY_FALLBACK = process.env.AUTO_CLAUDE_DISABLE_PROXY_FALLBACK !== 'true';

/**
 * Default proxy used when direct GitHub access fails and no custom proxy is provided
 */
export const DEFAULT_GITHUB_PROXY = 'https://mirror.ghproxy.com';

/**
 * Files and directories to preserve during updates
 */
export const PRESERVE_FILES = ['.env', 'specs', '.auto-claude', '.worktrees'] as const;

/**
 * Files and directories to skip when copying
 */
export const SKIP_FILES = [
  '__pycache__',
  '.DS_Store',
  '.git',
  'specs',
  '.env',
  '.auto-claude',
  '.worktrees'
] as const;

/**
 * Update-related timeouts (in milliseconds)
 */
export const TIMEOUTS = {
  requestTimeout: 10000,
  downloadTimeout: 60000
} as const;
