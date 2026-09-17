import { useEffect, useState } from 'react';
import { useChatStore } from '../stores/chat';
import { useFilesStore } from '../stores/files';
import { useSessionStore } from '../stores/session';
import FileEditor from './FileEditor';
import FileTree from './FileTree';
import FoldToggle from './FoldToggle';
import VscodePanel from './VscodePanel';

function RefreshBtn({ onClick }: { onClick: () => void }) {
  return (
    <button type="button" className="fold-btn" title="刷新" aria-label="刷新" onClick={onClick}>
      <svg width="16" height="16" viewBox="0 0 16 16" fill="none" aria-hidden>
        <path
          d="M13.2 8A5.2 5.2 0 0 1 4.6 11.4M2.8 8A5.2 5.2 0 0 1 11.4 4.6"
          stroke="currentColor"
          strokeWidth="1.6"
          strokeLinecap="round"
        />
        <path
          d="M4.6 13.1v-2.6H2M11.4 2.9v2.6H14"
          stroke="currentColor"
          strokeWidth="1.6"
          strokeLinecap="round"
          strokeLinejoin="round"
        />
      </svg>
    </button>
  );
}

export default function FilePanel({ onClose }: { onClose?: () => void }) {
  const current = useSessionStore((s) => s.current);
  const treeVersion = useChatStore((s) => s.treeVersion);
  const reloadRoot = useFilesStore((s) => s.reloadRoot);
  const openFile = useFilesStore((s) => s.openFile);
  const [tab, setTab] = useState<'files' | 'vscode'>('files');
  const [treeCollapsed, setTreeCollapsed] = useState(false);
  const [nonce, setNonce] = useState(0);
  const sid = current?.id;

  function refresh() {
    if (!sid) return;
    setNonce((n) => n + 1);
    void reloadRoot(sid);
  }

  useEffect(() => {
    if (treeVersion === 0) return;
    refresh();
  }, [treeVersion]);

  if (!current || !sid) return null;

  return (
    <div className="file-panel">
      <div className="file-tabs">
        <button className={`btn tiny ${tab === 'files' ? '' : 'ghost'}`} onClick={() => setTab('files')}>
          文件
        </button>
        <button className={`btn tiny ${tab === 'vscode' ? '' : 'ghost'}`} onClick={() => setTab('vscode')}>
          VS Code
        </button>
        {tab === 'vscode' || onClose ? <span className="ml-auto" /> : null}
        {tab === 'vscode' ? <RefreshBtn onClick={refresh} /> : null}
        {onClose ? (
          <button type="button" className="btn tiny" onClick={onClose}>
            收起
          </button>
        ) : null}
      </div>
      {tab === 'files' ? (
        <div className={`file-split${treeCollapsed ? ' tree-collapsed' : ''}`}>
          <div key={`tree-${sid}-${nonce}`} className="file-tree">
            <div className="file-tree-toolbar">
              <RefreshBtn onClick={refresh} />
              <FoldToggle
                collapsed={treeCollapsed}
                collapseLabel="收起目录"
                expandLabel="展开目录"
                onClick={() => setTreeCollapsed((v) => !v)}
              />
            </div>
            <div className="file-tree-body">
              <FileTree onOpen={(p) => void openFile(sid, p)} />
            </div>
          </div>
          <div className="editor-pane">
            <FileEditor />
          </div>
        </div>
      ) : (
        <VscodePanel key={`${sid}-${nonce}`} reloadKey={nonce} />
      )}
    </div>
  );
}
