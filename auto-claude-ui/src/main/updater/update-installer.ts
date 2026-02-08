/**
 * Update installation and application
 */

import { existsSync, mkdirSync, rmSync, readdirSync, readFileSync, createReadStream, renameSync } from 'fs';
import path from 'path';
import { createHash } from 'crypto';
import { app } from 'electron';
import { GITHUB_CONFIG, PRESERVE_FILES } from './config';
import { downloadFileWithFallback, fetchJsonWithFallback } from './http-client';
import { parseVersionFromTag } from './version-manager';
import { getUpdateCachePath, getUpdateTargetPath } from './path-resolver';
import { extractTarball, copyDirectoryRecursive, preserveFiles, restoreFiles } from './file-operations';
import { getCachedRelease, setCachedRelease, clearCachedRelease } from './update-checker';
import { GitHubRelease, AutoBuildUpdateResult, UpdateProgressCallback, UpdateMetadata, GitHubReleaseAsset } from './types';
import { debugLog } from '../../shared/utils/debug-logger';
import { writeJsonAtomic } from '../utils/atomic-write';

/**
 * Download and apply the latest auto-claude update from GitHub Releases
 *
 * Note: In production, this updates the bundled source in userData.
 * For packaged apps, we can't modify resourcesPath directly,
 * so we use a "source override" system.
 */
export async function downloadAndApplyUpdate(
  onProgress?: UpdateProgressCallback
): Promise<AutoBuildUpdateResult> {
  const cachePath = getUpdateCachePath();

  debugLog('[Update] Starting update process...');
  debugLog('[Update] Cache path:', cachePath);

  try {
    onProgress?.({
      stage: 'checking',
      message: 'Fetching release info...'
    });

    // Ensure cache directory exists
    if (!existsSync(cachePath)) {
      mkdirSync(cachePath, { recursive: true });
      debugLog('[Update] Created cache directory');
    }

    // Get release info (use cache or fetch fresh)
    let release = getCachedRelease();
    if (!release) {
      const releaseUrl = `https://api.github.com/repos/${GITHUB_CONFIG.owner}/${GITHUB_CONFIG.repo}/releases/latest`;
      debugLog('[Update] Fetching release info from:', releaseUrl);
      release = await fetchJsonWithFallback<GitHubRelease>(releaseUrl, GITHUB_CONFIG.proxyBase);
      setCachedRelease(release);
    } else {
      debugLog('[Update] Using cached release info');
    }

    // Use explicit tag reference URL to avoid HTTP 300 when branch/tag names collide
    // See: https://github.com/AndyMik90/Auto-Claude/issues/78
    const tarballUrl = `https://api.github.com/repos/${GITHUB_CONFIG.owner}/${GITHUB_CONFIG.repo}/tarball/refs/tags/${release.tag_name}`;
    const releaseVersion = parseVersionFromTag(release.tag_name);
    debugLog('[Update] Release version:', releaseVersion);
    debugLog('[Update] Tarball URL:', tarballUrl);

    const tarballPath = path.join(cachePath, 'auto-claude-update.tar.gz');
    const extractPath = path.join(cachePath, 'extracted');

    // Clean up previous extraction
    if (existsSync(extractPath)) {
      rmSync(extractPath, { recursive: true, force: true });
    }
    mkdirSync(extractPath, { recursive: true });

    onProgress?.({
      stage: 'downloading',
      percent: 0,
      message: 'Downloading update...'
    });

    debugLog('[Update] Starting download to:', tarballPath);

    // Download the tarball
    await downloadFileWithFallback(tarballUrl, tarballPath, (percent) => {
      onProgress?.({
        stage: 'downloading',
        percent,
        message: `Downloading... ${percent}%`
      });
    }, GITHUB_CONFIG.proxyBase);

    debugLog('[Update] Download complete');

    // Verify checksum if a checksum asset is published
    const checksumPath = path.join(cachePath, 'auto-claude-update.sha256');
    await verifyChecksumIfAvailable(release, tarballPath, checksumPath);

    onProgress?.({
      stage: 'extracting',
      message: 'Extracting update...'
    });

    debugLog('[Update] Extracting to:', extractPath);

    // Extract the tarball
    await extractTarball(tarballPath, extractPath);

    debugLog('[Update] Extraction complete');

    // Find the auto-claude folder in extracted content
    // GitHub tarballs have a root folder like "owner-repo-hash/"
    const extractedDirs = readdirSync(extractPath);
    if (extractedDirs.length === 0) {
      throw new Error('Empty tarball');
    }

    const rootDir = path.join(extractPath, extractedDirs[0]);
    const autoBuildSource = path.join(rootDir, GITHUB_CONFIG.autoBuildPath);

    if (!existsSync(autoBuildSource)) {
      throw new Error('auto-claude folder not found in download');
    }

    // Determine where to install the update
    const targetPath = getUpdateTargetPath();
    debugLog('[Update] Target install path:', targetPath);

    // Backup existing source (if in dev mode)
    const backupPath = path.join(cachePath, 'backup');
    if (!app.isPackaged && existsSync(targetPath)) {
      if (existsSync(backupPath)) {
        rmSync(backupPath, { recursive: true, force: true });
      }
      // Simple copy for backup
      debugLog('[Update] Creating backup at:', backupPath);
      copyDirectoryRecursive(targetPath, backupPath);
    }

    // Apply the update
    debugLog('[Update] Applying update...');
    await applyUpdate(targetPath, autoBuildSource);
    debugLog('[Update] Update applied successfully');

    // Write update metadata
    const metadata: UpdateMetadata = {
      version: releaseVersion,
      updatedAt: new Date().toISOString(),
      source: 'github-release',
      releaseTag: release.tag_name,
      releaseName: release.name
    };
    writeUpdateMetadata(targetPath, metadata);

    // Clear the cache after successful update
    clearCachedRelease();

    // Cleanup
    rmSync(tarballPath, { force: true });
    rmSync(checksumPath, { force: true });
    rmSync(extractPath, { recursive: true, force: true });

    onProgress?.({
      stage: 'complete',
      message: `Updated to version ${releaseVersion}`
    });

    debugLog('[Update] ============================================');
    debugLog('[Update] UPDATE SUCCESSFUL');
    debugLog('[Update] New version:', releaseVersion);
    debugLog('[Update] Target path:', targetPath);
    debugLog('[Update] ============================================');

    return {
      success: true,
      version: releaseVersion
    };
  } catch (error) {
    const errorMessage = error instanceof Error ? error.message : 'Update failed';
    debugLog('[Update] ============================================');
    debugLog('[Update] UPDATE FAILED');
    debugLog('[Update] Error:', errorMessage);
    debugLog('[Update] ============================================');

    onProgress?.({
      stage: 'error',
      message: errorMessage
    });

    return {
      success: false,
      error: error instanceof Error ? error.message : 'Unknown error'
    };
  }
}

function findChecksumAsset(release: GitHubRelease): GitHubReleaseAsset | null {
  const assets = release.assets || [];
  if (assets.length === 0) {
    return null;
  }

  const checksumAsset = assets.find(asset => /\.sha256(\.txt)?$/i.test(asset.name))
    || assets.find(asset => /sha256/i.test(asset.name));

  return checksumAsset || null;
}

function extractSha256(content: string, tarballName: string): string | null {
  const lines = content.split(/\r?\n/).map(line => line.trim()).filter(Boolean);
  let fallbackHash: string | null = null;

  for (const line of lines) {
    // Common formats:
    // 1) <hash>  <filename>
    // 2) SHA256 (filename) = <hash>
    const directMatch = line.match(/([a-fA-F0-9]{64})(?:\s+(.+))?/);
    if (directMatch) {
      const hash = directMatch[1].toLowerCase();
      const filePart = (directMatch[2] || '').trim();
      if (!filePart) {
        return hash;
      }
      if (filePart.includes(tarballName)) {
        return hash;
      }
      if (!fallbackHash) {
        fallbackHash = hash;
      }
    }

    const namedMatch = line.match(/SHA256\s*\((.+)\)\s*=\s*([a-fA-F0-9]{64})/i);
    if (namedMatch) {
      const fileName = namedMatch[1];
      const hash = namedMatch[2].toLowerCase();
      if (fileName.includes(tarballName)) {
        return hash;
      }
      if (!fallbackHash) {
        fallbackHash = hash;
      }
    }
  }

  return fallbackHash;
}

async function hashFileSha256(filePath: string): Promise<string> {
  return new Promise((resolve, reject) => {
    const hash = createHash('sha256');
    const stream = createReadStream(filePath);

    stream.on('data', (chunk) => hash.update(chunk));
    stream.on('error', reject);
    stream.on('end', () => resolve(hash.digest('hex')));
  });
}

async function verifyChecksumIfAvailable(
  release: GitHubRelease,
  tarballPath: string,
  checksumPath: string
): Promise<void> {
  const checksumAsset = findChecksumAsset(release);
  if (!checksumAsset) {
    debugLog('[Update] No checksum asset found; skipping verification');
    return;
  }

  debugLog('[Update] Found checksum asset:', checksumAsset.name);
  await downloadFileWithFallback(
    checksumAsset.browser_download_url,
    checksumPath,
    undefined,
    GITHUB_CONFIG.proxyBase
  );

  const checksumContent = readFileSync(checksumPath, 'utf-8');
  const expectedHash = extractSha256(checksumContent, path.basename(tarballPath));
  if (!expectedHash) {
    throw new Error('Checksum file found but no valid SHA256 hash could be parsed');
  }

  const actualHash = await hashFileSha256(tarballPath);
  if (actualHash !== expectedHash) {
    throw new Error('Checksum verification failed for downloaded update');
  }

  debugLog('[Update] Checksum verification passed');
}

/**
 * Apply update to target directory
 */
async function applyUpdate(targetPath: string, sourcePath: string): Promise<void> {
  const parentDir = path.dirname(targetPath);
  const stagingPath = path.join(parentDir, `.${path.basename(targetPath)}.staging-${Date.now()}`);
  const backupPath = path.join(parentDir, `.${path.basename(targetPath)}.backup`);
  let backupCreated = false;
  let targetSwapped = false;

  try {
    if (existsSync(stagingPath)) {
      rmSync(stagingPath, { recursive: true, force: true });
    }

    // Stage new files in a temporary directory first
    mkdirSync(stagingPath, { recursive: true });
    copyDirectoryRecursive(sourcePath, stagingPath, false);

    // Preserve important files from existing target
    if (existsSync(targetPath)) {
      const preservedContent = preserveFiles(targetPath, PRESERVE_FILES);
      restoreFiles(stagingPath, preservedContent);
    }

    verifyUpdateLayout(stagingPath);

    // Rotate backup if target exists
    if (existsSync(targetPath)) {
      if (existsSync(backupPath)) {
        rmSync(backupPath, { recursive: true, force: true });
      }
      renameSync(targetPath, backupPath);
      backupCreated = true;
    }

    // Atomic swap (same parent directory)
    renameSync(stagingPath, targetPath);
    targetSwapped = true;
    verifyUpdateLayout(targetPath);
  } catch (error) {
    // Best-effort rollback
    try {
      if ((backupCreated || targetSwapped) && existsSync(targetPath)) {
        rmSync(targetPath, { recursive: true, force: true });
      }
      if (backupCreated && existsSync(backupPath)) {
        renameSync(backupPath, targetPath);
      }
    } catch {
      // Ignore rollback failures
    }
    throw error;
  } finally {
    if (existsSync(stagingPath)) {
      rmSync(stagingPath, { recursive: true, force: true });
    }
  }
}

/**
 * Write update metadata to disk
 */
function writeUpdateMetadata(targetPath: string, metadata: UpdateMetadata): void {
  const metadataPath = path.join(targetPath, '.update-metadata.json');
  writeJsonAtomic(metadataPath, metadata);
}

function verifyUpdateLayout(targetPath: string): void {
  const requiredFiles = ['run.py', 'requirements.txt'];
  for (const file of requiredFiles) {
    if (!existsSync(path.join(targetPath, file))) {
      throw new Error(`Update missing required file: ${file}`);
    }
  }
}
