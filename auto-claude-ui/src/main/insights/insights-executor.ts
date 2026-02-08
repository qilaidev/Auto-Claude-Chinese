import { spawn, ChildProcess } from 'child_process';
import { existsSync, unlinkSync } from 'fs';
import path from 'path';
import os from 'os';
import { EventEmitter } from 'events';
import type {
  InsightsChatMessage,
  InsightsChatStatus,
  InsightsStreamChunk,
  InsightsToolUsage,
  InsightsModelConfig
} from '../../shared/types';
import { MODEL_ID_MAP } from '../../shared/constants';
import { InsightsConfig } from './config';
import { detectRateLimit, createSDKRateLimitInfo } from '../rate-limit-detector';
import { writeJsonAtomic } from '../utils/atomic-write';

const DEBUG = process.env.DEBUG === 'true' || process.env.NODE_ENV === 'development';

function redactSensitiveOutput(text: string): string {
  return text
    .replace(/\b[A-Z0-9]{4}[-\s][A-Z0-9]{4}\b/g, '****-****')
    .replace(/\bghp_[A-Za-z0-9]{20,}\b/g, 'ghp_***')
    .replace(/\bsk-[A-Za-z0-9]{20,}\b/g, 'sk-***')
    .replace(/\blin_api_[A-Za-z0-9]{10,}\b/g, 'lin_api_***')
    .replace(/\b(ANTHROPIC_AUTH_TOKEN|ANTHROPIC_API_KEY|CLAUDE_CODE_OAUTH_TOKEN)=[^\s\n\r]+/g, '$1=***');
}

function debug(message: string, data?: unknown): void {
  if (!DEBUG) return;
  if (data !== undefined) {
    console.warn(message, data);
  } else {
    console.warn(message);
  }
}

/**
 * Message processor result
 */
interface ProcessorResult {
  fullResponse: string;
  suggestedTask?: InsightsChatMessage['suggestedTask'];
  toolsUsed: InsightsToolUsage[];
}

/**
 * Python process executor for insights
 * Handles spawning and managing the Python insights runner process
 */
export class InsightsExecutor extends EventEmitter {
  private config: InsightsConfig;
  private activeSessions: Map<string, ChildProcess> = new Map();
  private readonly maxSessionMs = 70_000;

  constructor(config: InsightsConfig) {
    super();
    this.config = config;
  }

  /**
   * Check if a session is currently active
   */
  isSessionActive(projectId: string): boolean {
    return this.activeSessions.has(projectId);
  }

  /**
   * Cancel an active session
   */
  cancelSession(projectId: string): boolean {
    const existingProcess = this.activeSessions.get(projectId);
    if (!existingProcess) return false;

    existingProcess.kill();
    this.activeSessions.delete(projectId);
    return true;
  }

  /**
   * Execute insights query
   */
  async execute(
    projectId: string,
    projectPath: string,
    message: string,
    conversationHistory: Array<{ role: string; content: string }>,
    modelConfig?: InsightsModelConfig
  ): Promise<ProcessorResult> {
    // Cancel any existing session
    this.cancelSession(projectId);

    const autoBuildSource = this.config.getAutoBuildSourcePath();
    debug('[InsightsExecutor] autoBuildSource:', autoBuildSource);
    if (!autoBuildSource) {
      throw new Error('Auto Claude source not found');
    }

    const pythonPath = this.config.getPythonPath();
    debug('[InsightsExecutor] pythonPath:', pythonPath);

    const runnerPath = path.join(autoBuildSource, 'runners', 'insights_runner.py');
    debug('[InsightsExecutor] runnerPath:', runnerPath);
    if (!existsSync(runnerPath)) {
      throw new Error('insights_runner.py not found in auto-claude directory');
    }

    // Emit thinking status
    this.emit('status', projectId, {
      phase: 'thinking',
      message: 'Processing your message...'
    } as InsightsChatStatus);

    // Get process environment
    const processEnv = this.config.getProcessEnv();

    // Write conversation history to temp file to avoid Windows command-line length limit
    const historyFile = path.join(
      os.tmpdir(),
      `insights-history-${projectId}-${Date.now()}.json`
    );

    let historyFileCreated = false;
    try {
      writeJsonAtomic(historyFile, conversationHistory);
      historyFileCreated = true;
    } catch (err) {
      console.error('[Insights] Failed to write history file');
      debug('[Insights] write history file error:', err);
      throw new Error('Failed to write conversation history to temp file');
    }

    // Build command arguments
    const args = [
      runnerPath,
      '--project-dir', projectPath,
      '--message', message,
      '--history-file', historyFile
    ];

    // Add model config if provided
    if (modelConfig) {
      const modelId = MODEL_ID_MAP[modelConfig.model] || MODEL_ID_MAP['sonnet'];
      args.push('--model', modelId);
      args.push('--thinking-level', modelConfig.thinkingLevel);
    }

    // Spawn Python process
    debug('[InsightsExecutor] Spawning:', { pythonPath, args });
    const proc = spawn(this.config.getPythonPath(), args, {
      cwd: autoBuildSource,
      env: processEnv
    });

    this.activeSessions.set(projectId, proc);

    return new Promise((resolve, reject) => {
      let settled = false;
      let fullResponse = '';
      let suggestedTask: InsightsChatMessage['suggestedTask'] | undefined;
      const toolsUsed: InsightsToolUsage[] = [];
      let allInsightsOutput = '';

      const tailLines = (text: string, maxLines: number): string => {
        const trimmed = text.trim();
        if (!trimmed) return '';
        const lines = trimmed.split(/\r?\n/);
        return lines.slice(-maxLines).join('\n');
      };

      const emitErrorOnce = (error: string, err?: Error) => {
        if (settled) return;
        settled = true;

        this.emit('stream-chunk', projectId, {
          type: 'error',
          error
        } as InsightsStreamChunk);
        this.emit('error', projectId, error);
        reject(err || new Error(error));
      };

      const hardTimeout = setTimeout(() => {
        const details = tailLines(allInsightsOutput, 25);
        const error = details
          ? `Insights timed out after ${Math.round(this.maxSessionMs / 1000)}s\n${details}`
          : `Insights timed out after ${Math.round(this.maxSessionMs / 1000)}s`;

        try {
          proc.kill();
        } catch {
          // ignore
        }
        this.activeSessions.delete(projectId);

        // Cleanup temp file
        if (historyFileCreated && existsSync(historyFile)) {
          try {
            unlinkSync(historyFile);
          } catch {
            // ignore
          }
        }

        emitErrorOnce(error);
      }, this.maxSessionMs);

      proc.stdout?.on('data', (data: Buffer) => {
        const text = data.toString();
        // Collect output for rate limit detection (keep last 10KB)
        allInsightsOutput = (allInsightsOutput + text).slice(-10000);

        // Process output lines
        const lines = text.split('\n');
        for (const line of lines) {
          if (line.startsWith('__TASK_SUGGESTION__:')) {
            this.handleTaskSuggestion(projectId, line, (task) => {
              suggestedTask = task;
            });
          } else if (line.startsWith('__TOOL_START__:')) {
            this.handleToolStart(projectId, line, toolsUsed);
          } else if (line.startsWith('__TOOL_END__:')) {
            this.handleToolEnd(projectId, line);
          } else if (line.trim()) {
            fullResponse += line + '\n';
            this.emit('stream-chunk', projectId, {
              type: 'text',
              content: line + '\n'
            } as InsightsStreamChunk);
          }
        }
      });

      proc.stderr?.on('data', (data: Buffer) => {
        const text = data.toString();
        // Collect stderr for rate limit detection too
        allInsightsOutput = (allInsightsOutput + text).slice(-10000);
        debug('[Insights][stderr]', redactSensitiveOutput(text));
      });

      proc.on('close', (code) => {
        clearTimeout(hardTimeout);
        this.activeSessions.delete(projectId);

        // Cleanup temp file
        if (historyFileCreated && existsSync(historyFile)) {
          try {
            unlinkSync(historyFile);
          } catch (cleanupErr) {
            console.error('[Insights] Failed to cleanup history file');
            debug('[Insights] cleanup error:', cleanupErr);
          }
        }

        // Check for rate limit if process failed
        if (code !== 0) {
          this.handleRateLimit(projectId, allInsightsOutput);
        }

        if (settled) {
          return;
        }

        if (code === 0) {
          this.emit('stream-chunk', projectId, {
            type: 'done'
          } as InsightsStreamChunk);

          this.emit('status', projectId, {
            phase: 'complete'
          } as InsightsChatStatus);

          resolve({
            fullResponse: fullResponse.trim(),
            suggestedTask,
            toolsUsed
          });
        } else {
          const details = tailLines(allInsightsOutput, 25);
          const error = details
            ? `Process exited with code ${code}\n${details}`
            : `Process exited with code ${code}`;
          emitErrorOnce(error);
        }
      });

      proc.on('error', (err) => {
        clearTimeout(hardTimeout);
        this.activeSessions.delete(projectId);

        // Cleanup temp file
        if (historyFileCreated && existsSync(historyFile)) {
          try {
            unlinkSync(historyFile);
          } catch (cleanupErr) {
            console.error('[Insights] Failed to cleanup history file');
            debug('[Insights] cleanup error:', cleanupErr);
          }
        }

        emitErrorOnce(err.message, err);
      });
    });
  }

  /**
   * Handle task suggestion from output
   */
  private handleTaskSuggestion(
    projectId: string,
    line: string,
    onTaskFound: (task: InsightsChatMessage['suggestedTask']) => void
  ): void {
    try {
      const taskJson = line.substring('__TASK_SUGGESTION__:'.length);
      const suggestedTask = JSON.parse(taskJson);
      onTaskFound(suggestedTask);
      this.emit('stream-chunk', projectId, {
        type: 'task_suggestion',
        suggestedTask
      } as InsightsStreamChunk);
    } catch {
      // Not valid JSON, treat as normal text (should not emit here as it's already handled)
    }
  }

  /**
   * Handle tool start marker
   */
  private handleToolStart(
    projectId: string,
    line: string,
    toolsUsed: InsightsToolUsage[]
  ): void {
    try {
      const toolJson = line.substring('__TOOL_START__:'.length);
      const toolData = JSON.parse(toolJson);
      // Accumulate tool usage for persistence
      toolsUsed.push({
        name: toolData.name,
        input: toolData.input,
        timestamp: new Date()
      });
      this.emit('stream-chunk', projectId, {
        type: 'tool_start',
        tool: {
          name: toolData.name,
          input: toolData.input
        }
      } as InsightsStreamChunk);
    } catch {
      // Ignore parse errors for tool markers
    }
  }

  /**
   * Handle tool end marker
   */
  private handleToolEnd(projectId: string, line: string): void {
    try {
      const toolJson = line.substring('__TOOL_END__:'.length);
      const toolData = JSON.parse(toolJson);
      this.emit('stream-chunk', projectId, {
        type: 'tool_end',
        tool: {
          name: toolData.name
        }
      } as InsightsStreamChunk);
    } catch {
      // Ignore parse errors for tool markers
    }
  }

  /**
   * Handle rate limit detection
   */
  private handleRateLimit(projectId: string, output: string): void {
    const rateLimitDetection = detectRateLimit(output);
    if (rateLimitDetection.isRateLimited) {
      console.warn('[Insights] Rate limit detected:', {
        projectId,
        resetTime: rateLimitDetection.resetTime,
        limitType: rateLimitDetection.limitType,
        suggestedProfile: rateLimitDetection.suggestedProfile?.name
      });

      const rateLimitInfo = createSDKRateLimitInfo('other', rateLimitDetection, {
        projectId
      });
      this.emit('sdk-rate-limit', rateLimitInfo);
    }
  }
}
