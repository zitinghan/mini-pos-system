import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { ItemPicker, MenuItemButton } from './Session';
import { AvailabilityButton } from './Settings';
import type { MenuItem, Promotion } from '../services/types';

const promotion: Promotion = { id: 1, code: 'KOPI_TEH_RM1_2026', name: 'Kopi / Teh 限时优惠', unit_price: 100, starts_on: '2026-11-07', ends_on: '2026-12-01', skus: ['KOPI_O'], enabled: true, is_active: true };
const item: MenuItem = { id: 1, name: 'Kopi O', base_price: 100, regular_base_price: 230, promotion, groups: [
  { id: 1, name: '温度', minimum: 1, maximum: 1, options: [
    { id: 1, name: '热 HOT', price: 0, unit_price: 100, regular_unit_price: 230, is_default: true },
    { id: 2, name: '冰 ICED', price: 0, unit_price: 100, regular_unit_price: 260, is_default: false },
  ] },
] };

describe('scheduled drink prices and shared sold-out state', () => {
  it('shows both temperatures at RM1 with a promotion deadline and quantity total', () => {
    const add = vi.fn();
    render(<ItemPicker item={item} busy={false} onAdd={add} />);
    expect(screen.getByRole('button', { name: '热 HOT RM 1.00' })).toBeVisible();
    fireEvent.click(screen.getByRole('button', { name: '冰 ICED RM 1.00' }));
    expect(screen.getByText(/2026-12-01/)).toBeVisible();
    fireEvent.click(screen.getByRole('button', { name: '增加数量' }));
    fireEvent.click(screen.getByRole('button', { name: '加入草稿 · RM 2.00' }));
    expect(add).toHaveBeenCalledWith(2, [2]);
  });
  it('displays sold-out items and prevents selecting them', () => {
    const select = vi.fn();
    render(<MenuItemButton item={{ ...item, sold_out: true }} selected={false} onSelect={select} />);
    const card = screen.getByRole('button', { name: /Kopi O.*SOLD OUT/ });
    expect(card).toBeDisabled();
    fireEvent.click(card);
    expect(select).not.toHaveBeenCalled();
  });
  it('blocks an already-open picker when another device marks the item sold out', () => {
    const add = vi.fn();
    const view = render(<ItemPicker item={item} busy={false} onAdd={add} />);
    fireEvent.click(screen.getByRole('button', { name: '增加数量' }));
    view.rerender(<ItemPicker item={{ ...item, sold_out: true }} busy={false} onAdd={add} />);
    const button = screen.getByRole('button', { name: 'SOLD OUT · 已售罄' });
    expect(button).toBeDisabled();
    fireEvent.click(button);
    expect(add).not.toHaveBeenCalled();
    view.rerender(<ItemPicker item={{ ...item, sold_out: false }} busy={false} onAdd={add} />);
    expect(screen.getByRole('button', { name: '加入草稿 · RM 2.00' })).toBeEnabled();
  });
  it('provides an administrator control to restore supply', () => {
    const toggle = vi.fn();
    render(<AvailabilityButton item={{ ...item, sold_out: true }} pending={false} onToggle={toggle} />);
    fireEvent.click(screen.getByRole('button', { name: 'Kopi O · 恢复供应' }));
    expect(toggle).toHaveBeenCalledOnce();
  });
  it('prevents repeated stock changes while saving', () => {
    const toggle = vi.fn();
    render(<AvailabilityButton item={item} pending onToggle={toggle} />);
    const button = screen.getByRole('button', { name: 'Kopi O · 标记售罄' });
    expect(button).toBeDisabled();
    fireEvent.click(button);
    expect(toggle).not.toHaveBeenCalled();
  });
});
