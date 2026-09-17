export interface SessionInfo {
  id: string;
  user_name: string;
  git_url: string;
  base_branch: string;
  feature_branch: string;
  title: string;
  status: 'cloning' | 'ready' | 'running' | 'error' | 'restoring';
  error: string;
  created_at: string;
}

export interface TreeNode {
  name: string;
  path: string;
  type: 'dir' | 'file';
  size: number;
  children?: TreeNode[];
}

export type Block =
  | { kind: 'text'; text: string }
  | { kind: 'thinking'; text: string }
  | { kind: 'tool_use'; id: string; name: string; input: Record<string, unknown> }
  | { kind: 'tool_result'; tool_use_id: string; content: string; is_error: boolean };

export interface ChatMessage {
  id?: number;
  role: 'user' | 'assistant' | 'system' | 'result';
  blocks: Block[];
}
