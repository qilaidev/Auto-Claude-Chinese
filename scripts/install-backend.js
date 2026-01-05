#!/usr/bin/env node

const { spawnSync } = require('child_process');
const fs = require('fs');
const path = require('path');

function log(message) {
  console.log(message);
}

function error(message) {
  console.error(`❌ ${message}`);
  process.exit(1);
}

function splitCommand(command) {
  const parts = command.trim().split(/\s+/);
  return { cmd: parts[0], argsPrefix: parts.slice(1) };
}

function parsePythonVersion(output) {
  const match = output.match(/Python (\d+)\.(\d+)\.(\d+)/);
  if (!match) return null;
  return {
    major: Number(match[1]),
    minor: Number(match[2]),
    patch: Number(match[3])
  };
}

function isSupportedVersion(version) {
  return version.major === 3 && version.minor >= 10;
}

function detectPythonCommand() {
  const envPython = process.env.PYTHON || process.env.PYTHON_PATH;
  const candidates = [
    ...(envPython ? [envPython] : []),
    ...(process.platform === 'win32'
      ? ['py -3.12', 'py -3.11', 'py -3.10', 'py -3', 'python', 'python3']
      : ['python3.12', 'python3.11', 'python3.10', 'python3', 'python'])
  ];

  for (const candidate of candidates) {
    const { cmd, argsPrefix } = splitCommand(candidate);
    const result = spawnSync(cmd, [...argsPrefix, '--version'], {
      encoding: 'utf8',
      stdio: ['ignore', 'pipe', 'pipe'],
      windowsHide: true
    });

    if (result.status === 0) {
      const output = `${result.stdout || ''}${result.stderr || ''}`.trim();
      const version = parsePythonVersion(output);
      if (version && isSupportedVersion(version)) {
        return { cmd, argsPrefix, display: candidate, version: output };
      }
    }
  }

  return null;
}

function resolveBackendDir() {
  const candidates = [
    path.join(__dirname, '..', 'auto-claude'),
    path.join(__dirname, '..', 'apps', 'backend')
  ];

  for (const dir of candidates) {
    if (fs.existsSync(path.join(dir, 'requirements.txt'))) {
      return dir;
    }
  }
  return null;
}

const backendDir = resolveBackendDir();
if (!backendDir) {
  error('未找到后端目录（缺少 requirements.txt）。请确认 auto-claude/ 或 apps/backend/ 是否存在。');
}

const python = detectPythonCommand();
if (!python) {
  error('未找到 Python 3.10+。请安装后重试（Windows 可用 py -3.10+）。');
}

log(`✅ 使用 Python: ${python.display} (${python.version})`);
log(`📦 安装后端依赖: ${backendDir}`);

const requirementsPath = path.join(backendDir, 'requirements.txt');
const installResult = spawnSync(
  python.cmd,
  [...python.argsPrefix, '-m', 'pip', 'install', '-r', requirementsPath],
  {
    stdio: 'inherit',
    cwd: backendDir,
    windowsHide: true
  }
);

if (installResult.status !== 0) {
  error('后端依赖安装失败。');
}

log('✅ 后端依赖安装完成');
