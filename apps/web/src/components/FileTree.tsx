import { Tree } from 'antd';
import type { DataNode } from 'antd/es/tree';
import { useEffect } from 'react';
import { useFilesStore } from '../stores/files';
import { useSessionStore } from '../stores/session';
import type { TreeNode } from '../types';

function toDataNodes(nodes: TreeNode[]): DataNode[] {
  return nodes.map((n) => ({
    key: n.path,
    title: (
      <span className="file-tree-name" title={n.name}>
        {n.name}
      </span>
    ),
    isLeaf: n.type === 'file',
    children: n.children ? toDataNodes(n.children) : undefined,
  }));
}

export default function FileTree({ onOpen }: { onOpen: (path: string) => void }) {
  const current = useSessionStore((s) => s.current);
  const {
    treeData,
    expandedKeys,
    loadedKeys,
    setExpanded,
    markLoaded,
    loadTree,
  } = useFilesStore();

  useEffect(() => {
    if (current) void loadTree(current.id);
  }, [current?.id, loadTree]);

  if (!current) return null;
  return (
    <Tree
      blockNode
      indentSize={12}
      treeData={toDataNodes(treeData)}
      expandedKeys={expandedKeys}
      onExpand={(keys) => setExpanded(keys as string[])}
      loadData={(node) => {
        const path = node.key as string;
        if (!loadedKeys.includes(path)) {
          markLoaded(path);
          return loadTree(current.id, path);
        }
        return Promise.resolve();
      }}
      onSelect={(keys) => {
        const key = keys[0] as string | undefined;
        if (key) onOpen(key);
      }}
    />
  );
}
