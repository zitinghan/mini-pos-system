import { fireEvent, render, screen } from '@testing-library/react';
import { expect, it, vi } from 'vitest';
import { ItemPicker } from './Session';
import type { Line, MenuItem } from '../services/types';

const menu: MenuItem = { id: 1, name: '云吞面', base_price: 1200, groups: [
  { id: 1, name: '份量', minimum: 1, maximum: 1, options: [
    { id: 1, name: '普通', price: 0, is_default: true }, { id: 2, name: '加面', price: 200, is_default: false },
  ] },
  { id: 2, name: '用餐方式', minimum: 0, maximum: 1, options: [
    { id: 3, name: '堂食', price: 0, is_default: true }, { id: 4, name: '打包', price: 0, is_default: false },
  ] },
] };
const line: Line = { id: 5, menu_item_id: 1, name: '云吞面', quantity: 3, base_price: 800,
  unit_price: 800, line_total: 2400, status: 'SUBMITTED', revision: 2, notes: '原备注',
  modifiers: [{ option_id: 1, name: '普通', price: 0 }, { option_id: 3, name: '堂食', price: 0 }] };

it('prefills ordered quantities/notes and preserves the old unit price for free option edits', () => {
  const save = vi.fn();
  render(<ItemPicker item={menu} initial={line} onAdd={save} busy={false} />);
  expect(screen.getByLabelText('备注（可选）')).toHaveValue('原备注');
  fireEvent.click(screen.getByRole('button', { name: '打包' }));
  fireEvent.change(screen.getByLabelText('备注（可选）'), { target: { value: '改成打包' } });
  fireEvent.click(screen.getByRole('button', { name: '保存修改 · RM 24.00' }));
  expect(save).toHaveBeenCalledWith(3, [1, 4], '改成打包', 800);
});

it('shows the current configured price when changing a priced portion', () => {
  const save = vi.fn();
  render(<ItemPicker item={menu} initial={line} onAdd={save} busy={false} />);
  fireEvent.click(screen.getByRole('button', { name: /加面/ }));
  fireEvent.click(screen.getByRole('button', { name: '保存修改 · RM 42.00' }));
  expect(save).toHaveBeenCalledWith(3, [3, 2], '原备注', 1400);
});
