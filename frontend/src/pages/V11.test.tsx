import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { ItemPicker } from './Session';
import type { MenuItem } from '../services/types';

const drink: MenuItem = { id: 1, name: 'Kopi O', base_price: 230, category_code: 'DRINKS', groups: [
  { id: 1, name: '温度', minimum: 1, maximum: 1, options: [
    { id: 1, name: '热 HOT', price: 0, unit_price: 230, is_default: true },
    { id: 2, name: '冰 ICED', price: 0, unit_price: 450, is_default: false },
  ] },
] };

describe('v1.1 contextual ordering', () => {
  it('uses explicit temperature prices and multiplies by quantity', () => {
    const add = vi.fn();
    render(<ItemPicker item={drink} onAdd={add} busy={false} />);
    fireEvent.click(screen.getByRole('button', { name: /冰 ICED/ }));
    expect(screen.getByRole('button', { name: /热 HOT/ })).toHaveAttribute('aria-pressed', 'false');
    fireEvent.click(screen.getByRole('button', { name: '增加数量' }));
    fireEvent.click(screen.getByRole('button', { name: '加入草稿 · RM 9.00' }));
    expect(add).toHaveBeenCalledWith(2, [2]);
  });
  it('shows beer package quantities and physical bottles', () => {
    const beer: MenuItem = { id: 2, name: 'Carlsberg', base_price: 2200, groups: [{ id: 2, name: '包装', minimum: 1, maximum: 1, options: [
      { id: 3, name: '单瓶', price: 0, unit_price: 2200, bottles: 1, is_default: true },
      { id: 4, name: '3瓶', price: 0, unit_price: 6000, bottles: 3, is_default: false },
    ] }] };
    const add = vi.fn();
    render(<ItemPicker item={beer} onAdd={add} busy={false} />);
    fireEvent.click(screen.getByRole('button', { name: /3瓶/ }));
    fireEvent.click(screen.getByRole('button', { name: '增加数量' }));
    expect(screen.getByText('2 × 3瓶 · 共 6 瓶')).toBeVisible();
    fireEvent.click(screen.getByRole('button', { name: '加入草稿 · RM 120.00' }));
    expect(add).toHaveBeenCalledWith(2, [4]);
  });
  it('allows free water and preserves optional notes', () => {
    const water: MenuItem = { id: 3, name: '白开水', base_price: 0, complimentary: true, groups: [{ id: 3, name: '温度', minimum: 1, maximum: 1, options: [
      { id: 5, name: '冷', price: 0, unit_price: 0, is_default: true }, { id: 6, name: '热', price: 0, unit_price: 0, is_default: false },
    ] }] };
    const add = vi.fn();
    render(<ItemPicker item={water} onAdd={add} busy={false} />);
    fireEvent.change(screen.getByLabelText('备注（可选）'), { target: { value: '  少一点水  ' } });
    fireEvent.click(screen.getByRole('button', { name: '热 RM 0.00' }));
    fireEvent.click(screen.getByRole('button', { name: '加入草稿 · RM 0.00' }));
    expect(add).toHaveBeenCalledWith(1, [6], '少一点水');
  });
  it('supports optional multiple extras and prevents configured incompatible choices', () => {
    const food: MenuItem = { id: 4, name: '海南咖喱饭', base_price: 800, groups: [{ id: 4, name: '免费定制', minimum: 0, maximum: 3, options: [
      { id: 7, name: '不要菜', price: 0, is_default: false, incompatible_with: [8] },
      { id: 8, name: '换成鱼圆', price: 0, is_default: false },
      { id: 9, name: '加咖喱汁', price: 0, is_default: false },
    ] }] };
    const add = vi.fn();
    render(<ItemPicker item={food} onAdd={add} busy={false} />);
    fireEvent.click(screen.getByRole('button', { name: '不要菜' }));
    expect(screen.getByRole('button', { name: '换成鱼圆' })).toBeDisabled();
    fireEvent.click(screen.getByRole('button', { name: '加咖喱汁' }));
    fireEvent.click(screen.getByRole('button', { name: '加入草稿 · RM 8.00' }));
    expect(add).toHaveBeenCalledWith(1, [7, 9]);
  });
  it('lets a snack with no modifiers be ordered immediately', () => {
    const add = vi.fn();
    render(<ItemPicker item={{ id: 5, name: '炸云吞', description: '10粒', base_price: 700, groups: [] }} onAdd={add} busy={false} />);
    expect(screen.getByText('10粒')).toBeVisible();
    fireEvent.click(screen.getByRole('button', { name: '加入草稿 · RM 7.00' }));
    expect(add).toHaveBeenCalledWith(1, []);
  });
});
