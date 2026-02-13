import { useState, useEffect } from 'react';
import type { ProjectEnvConfig } from '../../shared/types';

export function useEnvironmentConfig(projectId: string, autoBuildPath: string | null, open: boolean) {
  const [envConfig, setEnvConfig] = useState<ProjectEnvConfig | null>(null);
  const [isLoadingEnv, setIsLoadingEnv] = useState(false);
  const [envError, setEnvError] = useState<string | null>(null);
  const [isSavingEnv, setIsSavingEnv] = useState(false);

  // Load environment config when dialog opens
  useEffect(() => {
    const loadEnvConfig = async () => {
      if (open && autoBuildPath) {
        setIsLoadingEnv(true);
        setEnvError(null);
        try {
          const result = await window.electronAPI.getProjectEnv(projectId);
          if (result.success && result.data) {
            setEnvConfig(result.data);
          } else {
            setEnvError(result.error || '加载环境配置失败');
          }
        } catch (err) {
          setEnvError(err instanceof Error ? err.message : '未知错误');
        } finally {
          setIsLoadingEnv(false);
        }
      }
    };
    loadEnvConfig();
  }, [open, projectId, autoBuildPath]);

  const updateEnvConfig = (updates: Partial<ProjectEnvConfig>) => {
    if (envConfig) {
      setEnvConfig({ ...envConfig, ...updates });
    }
  };

  const saveEnvConfig = async () => {
    if (!envConfig) return { success: false, error: '没有可保存的配置' };

    setIsSavingEnv(true);
    setEnvError(null);
    try {
      const result = await window.electronAPI.updateProjectEnv(projectId, envConfig);
      if (!result.success) {
        setEnvError(result.error || '保存环境配置失败');
        return { success: false, error: result.error };
      }
      return { success: true };
    } catch (err) {
      const error = err instanceof Error ? err.message : '未知错误';
      setEnvError(error);
      return { success: false, error };
    } finally {
      setIsSavingEnv(false);
    }
  };

  return {
    envConfig,
    setEnvConfig,
    updateEnvConfig,
    isLoadingEnv,
    envError,
    setEnvError,
    isSavingEnv,
    saveEnvConfig,
  };
}
