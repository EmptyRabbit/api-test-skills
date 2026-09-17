import { useEffect, useState } from 'react';
import { api } from '../api/client';
import { useSessionStore } from '../stores/session';

export default function VscodePanel({ reloadKey = 0 }: { reloadKey?: number }) {
  const current = useSessionStore((s) => s.current);
  const [ready, setReady] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    if (!current) return;
    setReady(false);
    setError('');
    void api
      .post(`/api/sessions/${current.id}/vscode/ensure`)
      .then(() => setReady(true))
      .catch((e: Error) => {
        setReady(false);
        setError(e.message || 'VS Code 启动失败');
      });
  }, [current?.id, reloadKey]);

  if (!current) return null;
  if (error) {
    return (
      <div className="empty">
        {error}
        <div className="note">本机需能拉起 code-server。文件页签仍可编辑。</div>
      </div>
    );
  }
  if (!ready) {
    return <div className="empty">正在启动 VS Code（首次约需数十秒）…</div>;
  }
  return (
    <div className="vscode-wrap">
      <iframe
        title="vscode"
        src={`/api/sessions/${current.id}/vscode/`}
        allow="clipboard-read; clipboard-write"
      />
    </div>
  );
}
