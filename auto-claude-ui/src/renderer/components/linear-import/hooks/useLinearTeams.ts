/**
 * Hook for loading Linear teams
 */

import { useState, useEffect } from 'react';
import type { LinearTeam } from '../types';

export function useLinearTeams(projectId: string, open: boolean) {
  const [teams, setTeams] = useState<LinearTeam[]>([]);
  const [isLoadingTeams, setIsLoadingTeams] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const loadTeams = async () => {
      if (!open) return;

      setIsLoadingTeams(true);
      setError(null);

      try {
        const result = await window.electronAPI.getLinearTeams(projectId);
        if (result.success && result.data) {
          setTeams(result.data);
        } else {
          setError(result.error || '加载团队失败');
        }
      } catch (err) {
        setError(err instanceof Error ? err.message : '未知错误');
      } finally {
        setIsLoadingTeams(false);
      }
    };

    loadTeams();
  }, [open, projectId]);

  return { teams, isLoadingTeams, error, setError };
}
