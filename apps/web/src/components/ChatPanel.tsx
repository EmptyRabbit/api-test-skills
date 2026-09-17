import { useEffect, useMemo, useRef, useState } from 'react';
import { isPreparing, repoName, statusClass, statusLabel } from '../status';
import { mergeToolResults } from '../mergeChat';
import { useChatStore } from '../stores/chat';
import { isMcpOAuthRequiredError, mcpOAuthReady, useMcpOAuthStore } from '../stores/mcpOAuth';
import { useSessionStore } from '../stores/session';
import MessageItem from './MessageItem';

type ChatPanelProps = {
  filesOpen: boolean;
  onToggleFiles: () => void;
};

function composerPlaceholder(busy: boolean, oauthOk: boolean): string {
  if (!oauthOk) return '请先完成顶部 MCP 授权';
  if (busy) return 'agent 运行中，可先输入下一句';
  return '继续下发任务，Enter 发送';
}

export default function ChatPanel({ filesOpen, onToggleFiles }: ChatPanelProps) {
  const current = useSessionStore((s) => s.current)!;
  const { messages, running, send, stop, attach, queued, setQueued, composerFill, setComposerFill } =
    useChatStore();
  const oauthLoaded = useMcpOAuthStore((s) => s.loaded);
  const oauthServers = useMcpOAuthStore((s) => s.servers);
  const oauthError = useMcpOAuthStore((s) => s.error);
  const oauthOk = mcpOAuthReady({ loaded: oauthLoaded, servers: oauthServers, error: oauthError });
  const [text, setText] = useState('');
  const bottomRef = useRef<HTMLDivElement>(null);
  const filesLabel = filesOpen ? '收起产物' : '产物';

  useEffect(() => {
    const detach = attach(current.id);
    return detach;
  }, [current.id, attach]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages.length]);

  useEffect(() => {
    if (composerFill == null) return;
    setText(composerFill);
    setComposerFill(null);
  }, [composerFill, setComposerFill]);

  useEffect(() => {
    if (queued == null) return;
    if (current.status === 'error') {
      setQueued(null);
      return;
    }
    if (current.status !== 'ready') return;
    if (!oauthOk) return;
    const t = queued;
    setQueued(null);
    void send(current.id, t);
  }, [queued, current.id, current.status, oauthOk, send, setQueued]);

  const busy = running || current.status === 'running';
  const ready = current.status === 'ready' && !busy && oauthOk;
  const canType = oauthOk && (current.status === 'ready' || current.status === 'running');
  const thread = useMemo(() => mergeToolResults(messages), [messages]);

  function submit() {
    if (!text.trim() || !ready) return;
    const t = text;
    setText('');
    void send(current.id, t).catch((e) => {
      if (!isMcpOAuthRequiredError(e)) setText(t);
    });
  }

  return (
    <>
      <div className="chat-top">
        <div className="title">{current.title || repoName(current.git_url)}</div>
        <span className={`status ${statusClass(current.status)}`}>{statusLabel(current.status)}</span>
        <div className="repo-pills">
          <span className="pill">
            {repoName(current.git_url)} {current.base_branch}→{current.feature_branch}
          </span>
        </div>
        <button className="btn ghost tiny ml-auto" onClick={onToggleFiles}>
          {filesLabel}
        </button>
      </div>
      <div className="thread-view">
        {isPreparing(current.status) && <div className="empty">工作区准备中…</div>}
        {current.status === 'error' && (
          <div className="empty">
            工作区准备失败
            <div className="note">{current.error || '克隆或恢复未完成'}</div>
          </div>
        )}
        {thread.map((m, i) => (
          <MessageItem key={m.id ?? i} message={m} />
        ))}
        <div ref={bottomRef} />
      </div>
      <div className="dock-composer">
        <div className="composer-wrap">
          <div className="composer">
            <textarea
              value={text}
              placeholder={composerPlaceholder(busy, oauthOk)}
              disabled={!canType}
              onChange={(e) => setText(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter' && !e.shiftKey && text.trim() && ready) {
                  e.preventDefault();
                  submit();
                }
              }}
            />
            <div className="composer-foot">
              <span className="hint">Enter 发送 · Shift+Enter 换行</span>
              {busy ? (
                <button className="btn danger" onClick={() => void stop(current.id)}>
                  停止
                </button>
              ) : (
                <button className="btn" disabled={!text.trim() || !ready} onClick={submit}>
                  发送
                </button>
              )}
            </div>
          </div>
        </div>
      </div>
    </>
  );
}
