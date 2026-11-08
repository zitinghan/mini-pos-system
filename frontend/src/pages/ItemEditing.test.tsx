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

it.each([['DRAFT',300],['SUBMITTED',330]])('drops retired canned temperatures from the editor and preserves %s pricing', (status,price) => {
  const save=vi.fn();
  const canned:MenuItem={id:2,name:'汽水 / 罐装',base_price:300,groups:[
    {id:8,name:'品牌 / 口味',minimum:0,maximum:1,options:[{id:10,name:'Coke',price:0,is_default:false}]},
    menu.groups[1],
  ]};
  const old:Line={...line,menu_item_id:2,name:canned.name,status:String(status),quantity:1,unit_price:330,line_total:330,
    modifiers:[{option_id:90,name:'冰 ICED',price:0},{option_id:10,name:'Coke',price:0},{option_id:3,name:'堂食',price:0}]};
  render(<ItemPicker item={canned} initial={old} onAdd={save} busy={false}/>);
  expect(screen.queryByRole('button',{name:/热 HOT|冰 ICED/})).not.toBeInTheDocument();
  fireEvent.click(screen.getByRole('button',{name:`保存修改 · RM ${(Number(price)/100).toFixed(2)}`}));
  expect(save).toHaveBeenCalledWith(1,[10,3],'原备注',Number(price));
});


it('uses replacement defaults and current price while retaining quantity and notes', () => {
  const save = vi.fn();
  const rice: MenuItem = { id: 9, name: 'Rice', base_price: 1500, groups: [
    { id: 9, name: 'Size', minimum: 1, maximum: 1, options: [
      { id: 91, name: 'Regular rice', price: 0, is_default: true },
    ] },
  ] };
  render(<ItemPicker item={rice} initial={line} onAdd={save} busy={false} />);
  expect(screen.getByRole('button', { name: 'Regular rice' })).toHaveAttribute('aria-pressed', 'true');
  fireEvent.click(screen.getByRole('button', { name: '保存修改 · RM 45.00' }));
  expect(save).toHaveBeenCalledWith(3, [91], line.notes, 1500);
});
