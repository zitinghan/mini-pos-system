import { act, fireEvent, render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import Checkout from './Checkout';

const state = vi.hoisted(() => ({ total: 2900, hasDrafts: false }));
vi.mock('@tanstack/react-query', () => ({
  useQuery: () => ({ data: { total: state.total, items: [], status: 'PAYMENT_PENDING', table: 'T05', has_drafts: state.hasDrafts }, isPending: false, isError: false }),
  useMutation: () => ({ mutate: vi.fn(), isPending: false }),
}));

function View() { return <MemoryRouter><Checkout /></MemoryRouter>; }

beforeEach(() => { state.total = 2900; state.hasDrafts = false; });

describe('checkout acknowledgement', () => {
  it('requires fresh confirmation after the polled bill changes', async () => {
    const view = render(<View />);
    fireEvent.click(screen.getByRole('button', { name: /^二维码$/ }));
    fireEvent.click(screen.getByRole('checkbox', { name: /人工核实/ }));
    fireEvent.click(screen.getByRole('button', { name: '确认收款并清台' }));
    expect(screen.getByRole('button', { name: /^确认$/ })).toBeEnabled();
    state.total = 3000;
    await act(async () => { view.rerender(<View />); });
    expect(screen.queryByRole('button', { name: /^确认$/ })).not.toBeInTheDocument();
    expect(screen.getByRole('checkbox', { name: /人工核实/ })).not.toBeChecked();
    expect(screen.getByRole('button', { name: '确认收款并清台' })).toBeDisabled();
  });
});
