import { message as antdMessage } from 'antd';
import { create } from 'zustand';
import { api } from '../api/client';
import type { TreeNode } from '../types';

interface FileState {
  expandedKeys: string[];
  loadedKeys: string[];
  treeData: TreeNode[];
  selected: string | null;
  openedContent: string | null;
  dirty: boolean;
  setExpanded: (keys: string[]) => void;
  markLoaded: (key: string) => void;
  reloadRoot: (sid: string) => Promise<void>;
  loadTree: (sid: string, path?: string) => Promise<void>;
  openFile: (sid: string, path: string) => Promise<void>;
  setContent: (content: string) => void;
  saveFile: (sid: string) => Promise<void>;
}

export const useFilesStore = create<FileState>((set, get) => ({
  expandedKeys: [],
  loadedKeys: [],
  treeData: [],
  selected: null,
  openedContent: null,
  dirty: false,

  setExpanded: (keys) => set({ expandedKeys: keys }),
  markLoaded: (key) =>
    set({ loadedKeys: [...new Set([...get().loadedKeys, key])] }),

  reloadRoot: async (sid) => {
    set({ loadedKeys: [], expandedKeys: [] });
    await get().loadTree(sid);
  },

  loadTree: async (sid, path = '') => {
    const nodes = await api.get<TreeNode[]>(
      `/api/sessions/${sid}/files/tree${path ? `?path=${encodeURIComponent(path)}` : ''}`
    );
    if (!path) {
      set({ treeData: nodes });
    } else {
      const merge = (list: TreeNode[], rel: string, children: TreeNode[]): TreeNode[] =>
        list.map((n) =>
          n.path === rel
            ? { ...n, children }
            : n.children
              ? { ...n, children: merge(n.children, rel, children) }
              : n
        );
      set({ treeData: merge(get().treeData, path, nodes) });
    }
  },

  openFile: async (sid, path) => {
    const data = await api.get<{ path: string; content: string }>(
      `/api/sessions/${sid}/files/content?path=${encodeURIComponent(path)}`
    );
    set({ selected: path, openedContent: data.content, dirty: false });
  },

  setContent: (content) =>
    set((_s) => ({
      openedContent: content,
      dirty: true,
    })),

  saveFile: async (sid) => {
    const { selected, openedContent } = get();
    if (!selected || openedContent === null) return;
    await api.put(`/api/sessions/${sid}/files/content`, {
      path: selected,
      content: openedContent,
    });
    set({ dirty: false });
    antdMessage.success('已保存');
  },
}));
