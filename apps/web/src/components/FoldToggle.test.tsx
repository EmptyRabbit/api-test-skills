import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import FoldToggle from './FoldToggle';

describe('FoldToggle', () => {
  it('toggles collapse with a compact icon button', () => {
    const onClick = vi.fn();
    const { rerender } = render(
      <FoldToggle collapsed={false} collapseLabel="收起目录" expandLabel="展开目录" onClick={onClick} />,
    );
    fireEvent.click(screen.getByRole('button', { name: '收起目录' }));
    expect(onClick).toHaveBeenCalledTimes(1);
    rerender(
      <FoldToggle collapsed collapseLabel="收起目录" expandLabel="展开目录" onClick={onClick} />,
    );
    expect(screen.getByRole('button', { name: '展开目录' })).toHaveAttribute('aria-expanded', 'false');
  });
});
