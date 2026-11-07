import { fireEvent, render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { describe, expect, it, vi } from 'vitest';
import Receipt, { ReceiptPaper } from './Receipt';
import type { CustomerReceipt } from '../services/types';

const data = vi.hoisted(() => ({ receipt: null as CustomerReceipt | null }));
vi.mock('@tanstack/react-query', () => ({
  useQuery: () => ({ data: data.receipt, isPending: false, error: null }),
  useQueryClient: () => ({ invalidateQueries: vi.fn() }),
  useMutation: () => ({ mutate: vi.fn(), isPending: false }),
}));
const receipt: CustomerReceipt = {
  kind: 'RECEIPT', payment_id: 12, session_id: 5, restaurant: '可可·南洋咖啡店', english_name: 'KE KE / KOPITIAM',
  receipt_number: 'R000012', table: 'T05', time: '2026-11-07T04:00:00+00:00', cashier: '收银员', currency: 'MYR',
  items: [{ id: 1, name: '云吞面', quantity: 2, base_price: 800, unit_price: 1000, line_total: 2000, status: 'SUBMITTED', modifiers: [{ name: '黑酱', price: 0, option_id: 1 }, { name: '加面', price: 200, option_id: 2 }] }],
  total: 2000, received: 5000, change: 3000, method: 'CASH', print_job: { id: 8, payment_id: 12, batch_id: null, status: 'SENT', attempts: 1, reprint: false, error: null, preview: null, created_at: '2026-11-07T04:00:00+00:00', printer_mode: 'mock' },
  print_history: [], configured_printer_mode: 'mock', paper_width: 576,
};

describe('customer receipt', () => {
  it('shows frozen item details, paid total, cash received and change', () => {
    render(<ReceiptPaper receipt={receipt} />);
    expect(screen.getByRole('article', { name: '客户收据' })).toBeVisible();
    expect(screen.getByText('R000012')).toBeVisible();
    expect(screen.getByText('2 × 云吞面')).toBeVisible();
    expect(screen.getByText('黑酱 · 加面')).toBeVisible();
    expect(screen.getByText('RM 50.00')).toBeVisible();
    expect(screen.getByText('RM 30.00')).toBeVisible();
  });
  it('supports browser printing and clearly labels simulated output', () => {
    data.receipt = receipt;
    const print = vi.spyOn(window, 'print').mockImplementation(() => undefined);
    render(<MemoryRouter><Receipt /></MemoryRouter>);
    expect(screen.getByText(/未发送到实体收银打印机/)).toBeVisible();
    fireEvent.click(screen.getByRole('button', { name: '浏览器打印 / 保存 PDF' }));
    expect(print).toHaveBeenCalledOnce();
    expect(screen.getByRole('link', { name: '← 返回桌台' })).toHaveAttribute('href', '/');
    print.mockRestore();
  });
  it('uses the configured 55mm receipt paper independently of kitchen paper', () => {
    data.receipt = { ...receipt, paper_width: 384, paper_mm: 55 };
    const { container } = render(<MemoryRouter><Receipt /></MemoryRouter>);
    expect(container.querySelector('.customer-receipt')).toHaveStyle('--receipt-width: 55mm');
    expect(container.querySelector('style')?.textContent).toContain('size: 55mm auto');
    expect(screen.getByText('RM 30.00')).toBeVisible();
  });
});
