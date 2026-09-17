import type { AnchorHTMLAttributes, ReactNode, TableHTMLAttributes } from 'react';
import { Children, isValidElement } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { CopyBtn } from './ChatIcons';
import './MarkdownBody.css';

const MARKDOWN_REMARK_PLUGINS = [remarkGfm];

function nodeText(node: ReactNode): string {
  if (node == null || typeof node === 'boolean') return '';
  if (typeof node === 'string' || typeof node === 'number') return String(node);
  if (Array.isArray(node)) return node.map(nodeText).join('');
  if (isValidElement<{ children?: ReactNode }>(node)) return nodeText(node.props.children);
  return '';
}

function fencedLanguage(children: ReactNode): string {
  const first = Children.toArray(children)[0];
  if (!isValidElement<{ className?: string }>(first)) return '';
  const className = first.props.className;
  if (typeof className !== 'string') return '';
  return className.replace(/^language-/, '').split(' ')[0] || '';
}

function FencedCode({ children }: { children?: ReactNode }) {
  return (
    <div className="md-codeblock">
      <div className="md-codeblock-head">
        <span>{fencedLanguage(children)}</span>
        <CopyBtn text={nodeText(children).replace(/\n$/, '')} />
      </div>
      <pre>{children}</pre>
    </div>
  );
}

const MARKDOWN_COMPONENTS = {
  a: ({ children, ...props }: AnchorHTMLAttributes<HTMLAnchorElement>) => (
    <a {...props} target="_blank" rel="noopener noreferrer">
      {children}
    </a>
  ),
  table: ({ children, ...props }: TableHTMLAttributes<HTMLTableElement>) => (
    <div className="markdown-body-table-wrap">
      <table {...props}>{children}</table>
    </div>
  ),
  pre: FencedCode,
};

export default function MarkdownView({ children }: { children: string }) {
  return (
    <div className="markdown-body">
      <ReactMarkdown remarkPlugins={MARKDOWN_REMARK_PLUGINS} components={MARKDOWN_COMPONENTS}>
        {children}
      </ReactMarkdown>
    </div>
  );
}
