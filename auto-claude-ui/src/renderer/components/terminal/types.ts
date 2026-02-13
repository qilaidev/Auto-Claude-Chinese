import type { Task, ExecutionPhase } from '../../../shared/types';
import type { TerminalStatus } from '../../stores/terminal-store';
import { Circle, Search, Code2, Wrench, CheckCircle2, AlertCircle } from 'lucide-react';

export interface TerminalProps {
  id: string;
  cwd?: string;
  projectPath?: string;
  isActive: boolean;
  onClose: () => void;
  onActivate: () => void;
  tasks?: Task[];
  onNewTaskClick?: () => void;
}

export const STATUS_COLORS: Record<TerminalStatus, string> = {
  idle: 'bg-warning',
  running: 'bg-success',
  'claude-active': 'bg-primary',
  exited: 'bg-destructive',
};

export const PHASE_CONFIG: Record<ExecutionPhase, { label: string; color: string; icon: React.ElementType }> = {
  idle: { label: '就绪', color: 'bg-muted text-muted-foreground', icon: Circle },
  planning: { label: '规划中', color: 'bg-info/20 text-info', icon: Search },
  coding: { label: '编码中', color: 'bg-primary/20 text-primary', icon: Code2 },
  qa_review: { label: '质量审查', color: 'bg-warning/20 text-warning', icon: Search },
  qa_fixing: { label: '修复中', color: 'bg-warning/20 text-warning', icon: Wrench },
  complete: { label: '完成', color: 'bg-success/20 text-success', icon: CheckCircle2 },
  failed: { label: '失败', color: 'bg-destructive/20 text-destructive', icon: AlertCircle },
};
