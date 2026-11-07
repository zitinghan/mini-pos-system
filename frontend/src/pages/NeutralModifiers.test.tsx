import { fireEvent, render, screen } from '@testing-library/react';
import { expect, it, vi } from 'vitest';
import { Lines } from '../components/Common';
import { ReceiptPaper } from './Receipt';
import { ItemPicker } from './Session';
import type { Line, MenuItem, CustomerReceipt } from '../services/types';

const line: Line = { id: 1, menu_item_id: 1, name: '面粉粿', quantity: 1, base_price: 800,
  unit_price: 800, line_total: 800, status: 'SUBMITTED', modifiers: [
    { option_id: 1, name: '汤', price: 0 }, { option_id: 2, name: '不加蛋', price: 0 },
    { option_id: 3, name: '普通', price: 0 }, { option_id: 4, name: '堂食', price: 0 },
  ] };

it('omits neutral labels on order lines and customer receipts while showing actual additions', () => {
  const added: Line = { ...line, id: 2, unit_price: 900, line_total: 900,
    modifiers: [{ option_id: 1, name: '汤', price: 0 }, { option_id: 5, name: '加蛋', price: 100 }, { option_id: 6, name: '打包', price: 0 }] };
  const receipt: CustomerReceipt = { kind: 'RECEIPT', payment_id: 1, session_id: 1, restaurant: '可可·南洋咖啡店',
    english_name: 'KE KE / KOPITIAM', receipt_number: 'R000001', table: 'T05', time: '2026-11-07T10:00:00+00:00',
    cashier: 'Owner', currency: 'MYR', items: [line, added], total: 1700, received: 1700, change: 0,
    method: 'QR', print_job: null, print_history: [], configured_printer_mode: 'mock', paper_width: 384 };
  render(<><Lines items={[line, added]} /><ReceiptPaper receipt={receipt} /></>);
  expect(screen.queryByText(/不加蛋|普通|堂食/)).not.toBeInTheDocument();
  expect(screen.getAllByText('汤')).toHaveLength(2);
  expect(screen.getAllByText('汤 · 加蛋 · 打包')).toHaveLength(2);
  expect(screen.getAllByText('RM 17.00')).toHaveLength(2);
});

it('keeps hidden defaults available when editing an existing order', () => {
  const edit = vi.fn();
  const view = render(<Lines items={[line]} onEdit={edit} />);
  fireEvent.click(screen.getByRole('button', { name: '修改 1 × 面粉粿' }));
  expect(edit).toHaveBeenCalledWith(line);
  view.unmount();
  const item: MenuItem = { id: 1, name: '面粉粿', base_price: 800, groups: [
    { id: 1, name: '做法', minimum: 1, maximum: 1, options: [{ id: 1, name: '汤', price: 0, is_default: true }] },
    { id: 2, name: '鸡蛋', minimum: 1, maximum: 1, options: [
      { id: 2, name: '不加蛋', price: 0, is_default: true }, { id: 5, name: '加蛋', price: 100, is_default: false },
    ] },
  ] };
  render(<ItemPicker item={item} initial={{ ...line, modifiers: line.modifiers.slice(0, 2) }} onAdd={vi.fn()} busy={false} />);
  expect(screen.getByRole('button', { name: '不加蛋' })).toHaveAttribute('aria-pressed', 'true');
});
