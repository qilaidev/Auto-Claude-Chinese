/**
 * Hook for managing the Linear import operation
 */

import { useState, useCallback } from 'react';
import type { LinearImportResult } from '../types';

export function useLinearImport(
  projectId: string,
  onImportComplete?: (result: LinearImportResult) => void
) {
  const [isImporting, setIsImporting] = useState(false);
  const [importResult, setImportResult] = useState<LinearImportResult | null>(null);
  const [error, setError] = useState<string | null>(null);

  const handleImport = useCallback(
    async (selectedIssueIds: Set<string>) => {
      if (selectedIssueIds.size === 0) return;

      setIsImporting(true);
      setError(null);
      setImportResult(null);

      try {
        const result = await window.electronAPI.importLinearIssues(
          projectId,
          Array.from(selectedIssueIds)
        );

        if (result.success && result.data) {
          setImportResult(result.data);
          if (result.data.success) {
            onImportComplete?.(result.data);
          }
        } else {
          setError(result.error || '导入问题失败');
        }
      } catch (err) {
        setError(err instanceof Error ? err.message : '未知错误');
      } finally {
        setIsImporting(false);
      }
    },
    [projectId, onImportComplete]
  );

  return {
    isImporting,
    importResult,
    error,
    setError,
    handleImport
  };
}
