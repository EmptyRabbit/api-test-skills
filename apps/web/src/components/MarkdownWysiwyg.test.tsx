import { render, waitFor } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import MarkdownWysiwyg from './MarkdownWysiwyg';

describe('MarkdownWysiwyg', () => {
  it('renders markdown content in the shared body typography', () => {
    const { container } = render(
      <MarkdownWysiwyg
        docKey="a.md"
        value={'# 标题\n\n| a | b |\n| --- | --- |\n| 1 | 2 |'}
        onChange={() => undefined}
      />,
    );
    const body = container.querySelector('.markdown-body');
    expect(body?.textContent).toContain('标题');
    expect(body?.textContent).toContain('1');
  });

  it('does not report a change just from loading the initial content', async () => {
    const onChange = vi.fn();
    render(<MarkdownWysiwyg docKey="a.md" value="# 标题" onChange={onChange} />);
    // The initial load round-trips through BlockNote's markdown parser, which
    // would otherwise fire onChange and mark a freshly opened file dirty.
    await waitFor(() => new Promise((resolve) => setTimeout(resolve, 10)));
    expect(onChange).not.toHaveBeenCalled();
  });
});
