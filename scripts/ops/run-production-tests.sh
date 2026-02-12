#!/usr/bin/env bash
# 生产目录关键回归测试集合（auto-claude / auto-claude-ui 相关）

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT_DIR/auto-claude"

if [[ -x ".venv/bin/pytest" ]]; then
  PYTEST_CMD=(".venv/bin/pytest")
else
  PYTEST_CMD=("python3" "-m" "pytest")
fi

TEST_CANDIDATES=(
  "../tests/test_auth_env.py"
  "../tests/test_backup.py"
  "../tests/test_backup_commands.py"
  "../tests/test_doctor_commands.py"
  "../tests/test_security.py"
  "../tests/test_workspace_merge_safety.py"
  "../tests/test_worktree.py"
  "../tests/test_platform.py"
  "../tests/test_git_executable.py"
  "../tests/test_phase_event.py"
)

TEST_FILES=()
for test_file in "${TEST_CANDIDATES[@]}"; do
  if [[ -f "$test_file" ]]; then
    TEST_FILES+=("$test_file")
  fi
done

if [[ "${#TEST_FILES[@]}" -eq 0 ]]; then
  echo "ERROR: no production test files were found in ../tests"
  exit 1
fi

"${PYTEST_CMD[@]}" "${TEST_FILES[@]}" -q
