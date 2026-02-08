import { basename, dirname, join } from 'path';
import { existsSync, mkdirSync, renameSync, unlinkSync, writeFileSync } from 'fs';

export type WriteFileOptions = Parameters<typeof writeFileSync>[2];

/**
 * Write a file atomically by writing to a temp file then renaming.
 * Use for persisted config/spec files that may be read by other processes.
 * Falls back to direct write if the atomic rename fails (e.g., on Windows).
 */
export function writeFileAtomic(
  targetPath: string,
  content: string | NodeJS.ArrayBufferView,
  options?: WriteFileOptions
): void {
  const dir = dirname(targetPath);
  if (!existsSync(dir)) {
    mkdirSync(dir, { recursive: true });
  }

  const tempPath = join(
    dir,
    `.${basename(targetPath)}.${process.pid}.${Date.now()}.tmp`
  );

  writeFileSync(tempPath, content, options);

  try {
    renameSync(tempPath, targetPath);
  } catch (error) {
    try {
      writeFileSync(targetPath, content, options);
    } finally {
      try {
        if (existsSync(tempPath)) {
          unlinkSync(tempPath);
        }
      } catch {
        // Best-effort cleanup; ignore.
      }
    }
  }
}

/**
 * Convenience for JSON files (plans, metadata, settings).
 */
export function writeJsonAtomic<T>(targetPath: string, data: T): void {
  writeFileAtomic(targetPath, JSON.stringify(data, null, 2));
}
