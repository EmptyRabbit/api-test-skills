import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import MarkdownView from './MarkdownView';

describe('MarkdownView', () => {
  it('renders gfm table inside a wrap', () => {
    const { container } = render(
      <MarkdownView>{'| 项 | 值 |\n| --- | --- |\n| operation | api/test |'}</MarkdownView>
    );
    expect(container.querySelector('.markdown-body-table-wrap')).toBeTruthy();
    expect(screen.getByText('operation')).toBeInTheDocument();
    expect(screen.getByText('api/test')).toBeInTheDocument();
  });

  it('renders fenced code with language and copy', () => {
    render(<MarkdownView>{'```powershell\nuvicorn app.main:app\n```'}</MarkdownView>);
    expect(screen.getByText('powershell')).toBeInTheDocument();
    expect(screen.getByText('uvicorn app.main:app')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: '复制' })).toBeInTheDocument();
  });

  it('renders headings and lists', () => {
    render(<MarkdownView>{'## 加载 vendor\n\n- 一项\n- 二项'}</MarkdownView>);
    expect(screen.getByRole('heading', { name: '加载 vendor' })).toBeInTheDocument();
    expect(screen.getByText('一项')).toBeInTheDocument();
  });
});
