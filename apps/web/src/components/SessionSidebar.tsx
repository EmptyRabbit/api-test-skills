import { repoName, statusLabel } from '../status';
import { useSessionStore } from '../stores/session';
import FoldToggle from './FoldToggle';

export default function SessionSidebar({
  collapsed,
  onToggle,
}: {
  collapsed: boolean;
  onToggle: () => void;
}) {
  const { sessions, current, openSession, clearCurrent } = useSessionStore();
  const foldToggle = (
    <FoldToggle
      collapsed={collapsed}
      collapseLabel="收起会话列表"
      expandLabel="展开会话列表"
      onClick={onToggle}
    />
  );

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
                <div className="t">{s.title || repoName(s.git_url) || s.id.slice(0, 8)}</div>
                <div className="s">
                  {statusLabel(s.status)} · {repoName(s.git_url)}
                </div>
              </div>
            ))}
          </div>
        </>
      )}
    </aside>
  );
}
