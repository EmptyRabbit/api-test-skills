import { useEffect } from 'react';
import { mcpOAuthReady, useMcpOAuthStore } from '../stores/mcpOAuth';

type Props = { userName: string };

export default function McpOAuthBar({ userName }: Props) {
  const { loaded, servers, flow, error, refresh, start, poll } = useMcpOAuthStore();
  const missing = servers.filter((s) => !s.authorized);

  useEffect(() => {
    void refresh(userName);
  }, [userName, refresh]);

  useEffect(() => {
    if (!flow) return;
    const ms = Math.max((flow.interval || 5) * 1000, 3000);
    let cancelled = false;
    let timer = 0;
    const tick = async () => {
      try {
        const st = await poll(flow.flow_id);
        if (cancelled) return;
        if (st === 'authorized') {
          void refresh(userName);
          return;
        }
        if (st !== 'pending') return;
      } catch {
        if (cancelled) return;
      }
      timer = window.setTimeout(() => void tick(), ms);
    };
    timer = window.setTimeout(() => void tick(), ms);
    return () => {
      cancelled = true;
      window.clearTimeout(timer);
    };
  }, [flow, poll, refresh, userName]);

  if (!userName.trim()) return null;
  if (loaded && servers.length === 0 && !error) return null;
  if (loaded && mcpOAuthReady({ loaded, servers, error }) && !error) return null;

  const pending = missing[0];

  return (
    <div className="mcp-oauth-bar">
      {flow ? (
        <>
          <span>
            在授权页完成登录：<strong>{flow.user_code}</strong>
          </span>
          <a href={flow.verification_uri_complete || flow.verification_uri} target="_blank" rel="noreferrer">
            打开授权页
          </a>
          <span className="note">完成后本页会自动继续；授权过的会话请新开，不要 resume 旧对话</span>
        </>
      ) : error ? (
        <>
          <span className="err">{error}</span>
          <button className="btn tiny" onClick={() => void refresh(userName)}>
            重试
          </button>
        </>
      ) : pending ? (
        <>
          <span>{pending.name} 需要授权后才能作为 MCP 使用</span>
          <button className="btn tiny" onClick={() => void start(userName, pending.name)}>
            授权
          </button>
        </>
      ) : (
        <span>正在检查 MCP 授权…</span>
      )}
    </div>
  );
}
