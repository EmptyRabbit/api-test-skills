import { useEffect, useState, type CSSProperties } from 'react';
import DrawerResizer from './components/DrawerResizer';
import ChatPanel from './components/ChatPanel';
import FilePanel from './components/FilePanel';
import HomePanel from './components/HomePanel';
import McpOAuthBar from './components/McpOAuthBar';
import SessionSidebar from './components/SessionSidebar';
import { clampDrawerWidth, readDrawerWidth, sidebarWidth, writeDrawerWidth } from './drawerWidth';
import { useSessionStore } from './stores/session';

export default function App() {
  const userName = useSessionStore((s) => s.userName);
  const setUserName = useSessionStore((s) => s.setUserName);
  const current = useSessionStore((s) => s.current);
  const loadSessions = useSessionStore((s) => s.loadSessions);
  const [filesOpen, setFilesOpen] = useState(false);
  const [sideCollapsed, setSideCollapsed] = useState(false);
  const sideW = sidebarWidth(sideCollapsed);
  const [drawerWidth, setDrawerWidth] = useState(() => readDrawerWidth(sideW));
  const [nameDraft, setNameDraft] = useState(userName);

  useEffect(() => {
    if (userName) void loadSessions();
  }, [userName, loadSessions]);

  useEffect(() => {
    if (!current) setFilesOpen(false);
  }, [current]);

  useEffect(() => {
    function sync() {
      setDrawerWidth((w) => clampDrawerWidth(w, undefined, sideW));
    }
    sync();
    window.addEventListener('resize', sync);
    return () => window.removeEventListener('resize', sync);
  }, [sideW]);

  function commitName() {
    const n = nameDraft.trim();
    if (n && n !== userName) setUserName(n);
  }

  return (
    <div className="app">
      <header className="menubar">
        <div className="brand">
          <span className="mark">测</span>
          智能测试平台
        </div>
        <span className="current-app">接口测试</span>
        <div className="who">
          <input
            value={nameDraft}
            placeholder="用户名"
            onChange={(e) => setNameDraft(e.target.value)}
            onBlur={commitName}
            onKeyDown={(e) => {
              if (e.key === 'Enter') (e.target as HTMLInputElement).blur();
            }}
          />
        </div>
      </header>
      <div className="shell">
        <McpOAuthBar userName={userName} />
        <div className={`body${sideCollapsed ? ' side-collapsed' : ''}`}>
          <SessionSidebar collapsed={sideCollapsed} onToggle={() => setSideCollapsed((v) => !v)} />
          <div
            className={`main ${filesOpen && current ? 'files' : ''}`}
            style={filesOpen && current ? ({ '--drawer-w': `${drawerWidth}px` } as CSSProperties) : undefined}
          >
            <section className="stage">
              {current ? (
                <ChatPanel
                  filesOpen={filesOpen}
                  onToggleFiles={() => setFilesOpen((v) => !v)}
                />
              ) : (
                <HomePanel />
              )}
            </section>
            <aside className="drawer">
              {filesOpen && current ? (
                <>
                  <DrawerResizer
                    width={drawerWidth}
                    clamp={(w) => clampDrawerWidth(w, undefined, sideW)}
                    onChange={setDrawerWidth}
                    onCommit={(w) => {
                      setDrawerWidth(w);
                      writeDrawerWidth(w, sideW);
                    }}
                  />
                  <FilePanel />
                </>
              ) : null}
            </aside>
          </div>
        </div>
      </div>
    </div>
  );
}
