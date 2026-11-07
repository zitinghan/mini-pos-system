import { act, fireEvent, render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import Checkout from './Checkout';

const state = vi.hoisted(() => ({ total: 2900, hasDrafts: false, mutate: vi.fn() }));
vi.mock('@tanstack/react-query', () => ({
  useQuery: () => ({ data: { total: state.total, item_count: 1, items: [], status: 'PAYMENT_PENDING', table: 'T05', has_drafts: state.hasDrafts }, isPending: false, isError: false }),
  useMutation: () => ({ mutate: state.mutate, isPending: false }),
}));
function View() { return <MemoryRouter><Checkout /></MemoryRouter>; }
beforeEach(() => { state.total = 2900; state.hasDrafts = false; state.mutate.mockReset(); });

describe('single-step QR checkout', () => {
  it('defaults to QR without a checkbox or extra confirmation dialog', () => {
    render(<View />);
    expect(screen.getByRole('button', { name: /^二维码$/ })).toHaveAttribute('aria-pressed', 'true');
    expect(screen.queryByRole('checkbox', { name: /人工核实/ })).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: '确认收款并清台' }));
    expect(state.mutate).toHaveBeenCalledOnce();
    expect(screen.queryByRole('button', { name: /^确认$/ })).not.toBeInTheDocument();
  });
  it('still validates cash before allowing payment', () => {
    render(<View />);
    fireEvent.click(screen.getByRole('button', { name: '现金' }));
    expect(screen.getByRole('button', { name: '确认收款并清台' })).toBeDisabled();
    fireEvent.change(screen.getByLabelText('收到现金 (RM)'), { target: { value: '50.00' } });
    expect(screen.getByRole('button', { name: '确认收款并清台' })).toBeEnabled();
  });
  it('uses current polled totals and retains explicit draft discard', async () => {
    const view = render(<View />);
    state.total = 3000; state.hasDrafts = true;
    await act(async () => { view.rerender(<View />); });
    expect(screen.getByRole('heading', { name: 'RM 30.00' })).toBeVisible();
    expect(screen.getByRole('button', { name: '确认收款并清台' })).toBeDisabled();
    fireEvent.click(screen.getByRole('checkbox', { name: /丢弃本桌全部草稿/ }));
    expect(screen.getByRole('button', { name: '确认收款并清台' })).toBeEnabled();
  });
  it('allows a submitted complimentary order to settle at zero', () => {
    state.total = 0;
    render(<View />);
    expect(screen.getByRole('button', { name: '确认收款并清台' })).toBeEnabled();
  });
});
