import { message as antdMessage } from 'antd';
import type { MouseEvent } from 'react';
import { repoName, statusLabel } from '../status';
import { useSessionStore } from '../stores/session';
import FoldToggle from './FoldToggle';

function TrashIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 16 16" fill="none" aria-hidden>
      <path
        d="M3.5 4.5h9M6.5 4.5V3.2a.7.7 0 0 1 .7-.7h1.6a.7.7 0 0 1 .7.7v1.3M5.2 6.2v6.1c0 .4.3.7.7.7h4.2c.4 0 .7-.3.7-.7V6.2M6.8 7.3v4M9.2 7.3v4"
        stroke="currentColor"
        strokeWidth="1.3"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

export default function SessionSidebar({
  collapsed,
  onToggle,
}: {
  collapsed: boolean;
  onToggle: () => void;
}) {
  const { sessions, current, openSession, clearCurrent, deleteSession } = useSessionStore();
  const foldToggle = (
    <FoldToggle
      collapsed={collapsed}
      collapseLabel="收起会话列表"
      expandLabel="展开会话列表"
      onClick={onToggle}
    />
  );

  async function onDelete(ev: MouseEvent, sid: string) {
    ev.stopPropagation();
    if (!window.confirm('删除后无法恢复，将同时清除该会话的数据库记录和工作区文件。确定删除？')) {
      return;
    }
    try {
      await deleteSession(sid);
    } catch (e) {
      antdMessage.error(`删除失败：${(e as Error).message}`);
    }
  }

  return (
    <aside className={`side${collapsed ? ' collapsed' : ''}`}>
      <div className="side-head">
        {collapsed ? (
          <>
            {foldToggle}
            <button type="button" className="fold-btn" title="新会话" aria-label="新会话" onClick={() => clearCurrent()}>
              <svg width="16" height="16" viewBox="0 0 16 16" fill="none" aria-hidden>
                <path
                  d="M8 3.5v9M3.5 8h9"
                  stroke="currentColor"
                  strokeWidth="1.6"
                  strokeLinecap="round"
                />
              </svg>
            </button>
          </>
        ) : (
          <>
            <button className={`side-btn ${current ? '' : 'on'}`} onClick={() => clearCurrent()}>
              ＋ 新会话
            </button>
            {foldToggle}
          </>
        )}
      </div>
      {!collapsed && (
        <>
          <h4>最近</h4>
          <div className="threads">
            {sessions.map((s) => (
              <div
                key={s.id}
                className={`thread ${current?.id === s.id ? 'on' : ''}`}
                onClick={() => void openSession(s.id)}
              >
                <div className="thread-body">
                  <div className="t">{s.title || repoName(s.git_url) || s.id.slice(0, 8)}</div>
                  <div className="s">
                    {statusLabel(s.status)} · {repoName(s.git_url)}
                  </div>
                </div>
                <button
                  type="button"
                  className="thread-del"
                  title="删除会话"
                  aria-label="删除会话"
                  onClick={(ev) => void onDelete(ev, s.id)}
                >
                  <TrashIcon />
                </button>
              </div>
            ))}
          </div>
        </>
      )}
    </aside>
  );
}
