import { useState } from 'react';
import { GitMerge, ExternalLink, Copy, Check, Sparkles } from 'lucide-react';
import { Button } from '../../ui/button';
import { Textarea } from '../../ui/textarea';
import type { Task } from '../../../../shared/types';

interface StagedSuccessMessageProps {
  stagedSuccess: string;
  stagedProjectPath: string | undefined;
  task: Task;
  suggestedCommitMessage?: string;
}

/**
 * Displays success message after changes have been staged in the main project
 */
export function StagedSuccessMessage({
  stagedSuccess,
  stagedProjectPath,
  task,
  suggestedCommitMessage
}: StagedSuccessMessageProps) {
  const [commitMessage, setCommitMessage] = useState(suggestedCommitMessage || '');
  const [copied, setCopied] = useState(false);

  const handleCopy = async () => {
    if (!commitMessage) return;
    try {
      await navigator.clipboard.writeText(commitMessage);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch (err) {
      console.error('复制失败：', err);
    }
  };

  return (
    <div className="rounded-xl border border-success/30 bg-success/10 p-4">
      <h3 className="font-medium text-sm text-foreground mb-2 flex items-center gap-2">
        <GitMerge className="h-4 w-4 text-success" />
        更改已成功暂存
      </h3>
      <p className="text-sm text-muted-foreground mb-3">
        {stagedSuccess}
      </p>

      {/* Commit Message Section */}
      {suggestedCommitMessage && (
        <div className="bg-background/50 rounded-lg p-3 mb-3">
          <div className="flex items-center justify-between mb-2">
            <p className="text-xs text-muted-foreground flex items-center gap-1.5">
              <Sparkles className="h-3 w-3 text-purple-400" />
              AI 生成的提交信息
            </p>
            <Button
              variant="ghost"
              size="sm"
              onClick={handleCopy}
              className="h-6 px-2 text-xs"
              disabled={!commitMessage}
            >
              {copied ? (
                <>
                  <Check className="h-3 w-3 mr-1 text-success" />
                  已复制！
                </>
              ) : (
                <>
                  <Copy className="h-3 w-3 mr-1" />
                  复制
                </>
              )}
            </Button>
          </div>
          <Textarea
            value={commitMessage}
            onChange={(e) => setCommitMessage(e.target.value)}
            className="font-mono text-xs min-h-[100px] bg-background/80 resize-y"
            placeholder="提交信息..."
          />
          <p className="text-[10px] text-muted-foreground mt-1.5">
            按需修改后复制，并用于 <code className="bg-background px-1 rounded">git commit -m "..."</code>
          </p>
        </div>
      )}

      <div className="bg-background/50 rounded-lg p-3 mb-3">
        <p className="text-xs text-muted-foreground mb-2">下一步：</p>
        <ol className="text-xs text-muted-foreground space-y-1 list-decimal list-inside">
          <li>在 IDE 或终端打开项目</li>
          <li>使用 <code className="bg-background px-1 rounded">git status</code> 和 <code className="bg-background px-1 rounded">git diff --staged</code> 查看暂存更改</li>
          <li>确认无误后提交：<code className="bg-background px-1 rounded">git commit -m "你的提交信息"</code></li>
        </ol>
      </div>
      {stagedProjectPath && (
        <Button
          variant="outline"
          size="sm"
          onClick={() => {
            window.electronAPI.createTerminal({
              id: `project-${task.id}`,
              cwd: stagedProjectPath
            });
          }}
          className="w-full"
        >
          <ExternalLink className="mr-2 h-4 w-4" />
          在终端打开项目
        </Button>
      )}
    </div>
  );
}
