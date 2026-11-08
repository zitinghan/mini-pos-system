import { act, fireEvent, render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import Checkout from './Checkout';

const state = vi.hoisted(() => ({ total: 2900, prepaid: 0, hasDrafts: false, mutate: vi.fn() }));
vi.mock('@tanstack/react-query', () => ({
  useQuery: () => ({ data: { total: state.total, prepaid_total: state.prepaid, item_count: 1, items: [], status: 'PAYMENT_PENDING', table: 'T05', has_drafts: state.hasDrafts }, isPending: false, isError: false }),
  useMutation: () => ({ mutate: state.mutate, isPending: false }),
}));
function View() { return <MemoryRouter><Checkout /></MemoryRouter>; }
beforeEach(() => { state.total = 2900; state.prepaid = 0; state.hasDrafts = false; state.mutate.mockReset(); });

describe('single-step QR checkout', () => {
  it('shows paid and remaining amounts and only validates cash for the balance', () => {
    state.prepaid = 2000;
    render(<View />);
    expect(screen.getByText('已付金额').parentElement).toHaveTextContent('RM 20.00');
    expect(screen.getByText('剩余应收').parentElement).toHaveTextContent('RM 9.00');
    fireEvent.click(screen.getByRole('button', {name:'现金'}));
    fireEvent.change(screen.getByLabelText('收到现金 (RM)'), {target:{value:'10'}});
    expect(screen.getByText('应找零').parentElement).toHaveTextContent('RM 1.00');
    expect(screen.getByRole('button', {name:'确认收款并清台'})).toBeEnabled();
  });
  it('hides payment selection for full payment and restores it if an add-on increases the total', async () => {
    state.prepaid = 2900;
    const view = render(<View />);
    expect(screen.getByText('剩余应收').parentElement).toHaveTextContent('RM 0.00');
    expect(screen.queryByRole('button', {name:'二维码'})).not.toBeInTheDocument();
    expect(screen.queryByLabelText('收到现金 (RM)')).not.toBeInTheDocument();
    expect(screen.getByRole('button', {name:'确认已付款并清台'})).toBeEnabled();
    state.total = 3200;
    await act(async () => {view.rerender(<View />);});
    expect(screen.getByText('剩余应收').parentElement).toHaveTextContent('RM 3.00');
    expect(screen.getByRole('button', {name:'二维码'})).toBeVisible();
  });
  it('warns about excess prepaid money but allows settlement without collecting again', () => {
    state.prepaid = 2000;
    render(<View />);
    fireEvent.change(screen.getByLabelText('优惠后总价 (RM)'), {target:{value:'19.00'}});
    expect(screen.getByRole('alert')).toHaveTextContent('已付超过应付');
    expect(screen.getByRole('alert')).toHaveTextContent('RM 1.00');
    fireEvent.click(screen.getByRole('button', {name:'确认已付款并清台'}));
    expect(state.mutate).toHaveBeenCalledOnce();
  });
  it('defaults to QR without a checkbox or extra confirmation dialog', () => {
    render(<View />);
    expect(screen.getByRole('button', { name: /^二维码$/ })).toHaveAttribute('aria-pressed', 'true');
    expect(screen.queryByRole('checkbox', { name: /人工核实/ })).not.toBeInTheDocument();
    expect(screen.getByRole('checkbox', { name:'打印收据（默认不打印）' })).not.toBeChecked();
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
  it('uses an entered offer for cash validation and resets it when the bill changes', async () => {
    const view = render(<View />);
    fireEvent.change(screen.getByLabelText('优惠后总价 (RM)'), { target: { value: '20.00' } });
    expect(screen.getByRole('heading', { name: 'RM 20.00' })).toBeVisible();
    fireEvent.click(screen.getByRole('button', { name: '现金' }));
    fireEvent.change(screen.getByLabelText('收到现金 (RM)'), { target: { value: '25.00' } });
    expect(screen.getByText('RM 5.00')).toBeVisible();
    expect(screen.getByRole('button', { name: '确认收款并清台' })).toBeEnabled();
    state.total = 3000;
    await act(async () => { view.rerender(<View />); });
    expect(screen.getByLabelText('优惠后总价 (RM)')).toHaveValue('30.00');
    expect(screen.getByRole('button', { name: '确认收款并清台' })).toBeDisabled();
  });
  it('rejects invalid offers, permits a full discount and restores the original amount', () => {
    render(<View />);
    for (const value of ['30.00', '-1', '1.234', '']) {
      fireEvent.change(screen.getByLabelText('优惠后总价 (RM)'), { target: { value } });
      expect(screen.getByRole('button', { name: '确认收款并清台' })).toBeDisabled();
    }
    fireEvent.change(screen.getByLabelText('优惠后总价 (RM)'), { target: { value: '0' } });
    expect(screen.getByRole('button', { name: '确认收款并清台' })).toBeEnabled();
    fireEvent.click(screen.getByRole('button', { name: '恢复原价' }));
    expect(screen.getByLabelText('优惠后总价 (RM)')).toHaveValue('29.00');
  });
});
