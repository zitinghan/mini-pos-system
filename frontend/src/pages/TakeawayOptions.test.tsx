import { fireEvent, render, screen } from '@testing-library/react';
import { expect, it, vi } from 'vitest';
import { ItemPicker } from './Session';
import type { MenuItem } from '../services/types';

const drink: MenuItem = { id: 1, name: 'Kopi O', base_price: 230, groups: [
  { id: 1, name: '温度', minimum: 1, maximum: 1, options: [
    { id: 1, name: '热 HOT', price: 0, unit_price: 230, is_default: true },
    { id: 2, name: '冰 ICED', price: 0, unit_price: 260, is_default: false },
  ] },
  { id: 2, name: '甜度', minimum: 0, maximum: 1, options: [
    { id: 3, name: 'Kosong（不加糖）', price: 0, is_default: false },
    { id: 4, name: 'Siu Dai（少甜）', price: 0, is_default: false },
  ] },
  { id: 3, name: '浓度', minimum: 0, maximum: 1, options: [{ id: 5, name: 'Kao（加浓）', price: 0, is_default: false }] },
  { id: 4, name: '冰量', minimum: 0, maximum: 1, options: [
    { id: 6, name: '少冰 Less Ice', price: 0, is_default: false, incompatible_with: [1] },
    { id: 7, name: '去冰 No Ice', price: 0, is_default: false, incompatible_with: [1] },
  ] },
  { id: 5, name: '用餐方式', minimum: 0, maximum: 1, options: [
    { id: 8, name: '堂食', price: 0, is_default: true }, { id: 9, name: '打包', price: 0, is_default: false },
  ] },
] };

it('shows optional soup separation only for takeaway and clears it when returning to dine-in',()=>{
  const add=vi.fn();
  const kueh:MenuItem={id:2,name:'面粉粿',sku:'MEE_HOON_KUEH',base_price:800,groups:[
    {id:10,name:'用餐方式',minimum:0,maximum:1,options:[
      {id:11,name:'堂食',price:0,is_default:true},{id:12,name:'打包',price:0,is_default:false}]},
    {id:20,name:'打包设置',minimum:0,maximum:1,options:[
      {id:21,name:'汤分开',price:0,is_default:false,incompatible_with:[11]}]},
  ]};
  render(<ItemPicker item={kueh} busy={false} onAdd={add}/>);
  expect(screen.queryByRole('button',{name:'汤分开'})).not.toBeInTheDocument();
  fireEvent.click(screen.getByRole('button',{name:'打包'}));
  expect(screen.getByRole('button',{name:'汤分开'})).toHaveAttribute('aria-pressed','false');
  fireEvent.click(screen.getByRole('button',{name:'汤分开'}));
  expect(screen.getByRole('button',{name:'加入草稿 · RM 8.00'})).toBeEnabled();
  expect(screen.getByRole('button',{name:'堂食'})).toBeEnabled();
  fireEvent.click(screen.getByRole('button',{name:'堂食'}));
  expect(screen.queryByRole('button',{name:'汤分开'})).not.toBeInTheDocument();
  fireEvent.click(screen.getByRole('button',{name:'打包'}));
  expect(screen.getByRole('button',{name:'汤分开'})).toHaveAttribute('aria-pressed','false');
  fireEvent.click(screen.getByRole('button',{name:'汤分开'}));
  fireEvent.click(screen.getByRole('button',{name:'加入草稿 · RM 8.00'}));
  expect(new Set(add.mock.calls[0][1])).toEqual(new Set([12,21]));
});

it('shows packing first, allows one sweetness with Kao and keeps the configured price', () => {
  const add = vi.fn();
  const { container } = render(<ItemPicker item={drink} onAdd={add} busy={false} />);
  expect(container.querySelector('legend')).toHaveTextContent('用餐方式');
  expect(screen.getByRole('button', { name: '堂食' })).toHaveAttribute('aria-pressed', 'true');
  fireEvent.click(screen.getByRole('button', { name: '堂食' }));
  expect(screen.getByRole('button', { name: '堂食' })).toHaveAttribute('aria-pressed', 'true');
  fireEvent.click(screen.getByRole('button', { name: '打包' }));
  expect(screen.getByRole('button', { name: '堂食' })).toHaveAttribute('aria-pressed', 'false');
  fireEvent.click(screen.getByRole('button', { name: /冰 ICED/ }));
  fireEvent.click(screen.getByRole('button', { name: /Kosong/ }));
  fireEvent.click(screen.getByRole('button', { name: /Siu Dai/ }));
  expect(screen.getByRole('button', { name: /Kosong/ })).toHaveAttribute('aria-pressed', 'false');
  fireEvent.click(screen.getByRole('button', { name: /Kao/ }));
  fireEvent.click(screen.getByRole('button', { name: /少冰/ }));
  fireEvent.click(screen.getByRole('button', { name: '增加数量' }));
  fireEvent.click(screen.getByRole('button', { name: '加入草稿 · RM 5.20' }));
  expect(new Set(add.mock.calls[0][1])).toEqual(new Set([2, 4, 5, 6, 9]));
  expect(add.mock.calls[0][0]).toBe(2);
});

it('limits ice to one choice and clears it when switching to hot, preserving other choices', () => {
  const add = vi.fn();
  render(<ItemPicker item={drink} onAdd={add} busy={false} />);
  expect(screen.queryByRole('button', { name: /少冰/ })).not.toBeInTheDocument();
  fireEvent.click(screen.getByRole('button', { name: /冰 ICED/ }));
  fireEvent.click(screen.getByRole('button', { name: /少冰/ }));
  fireEvent.click(screen.getByRole('button', { name: /去冰/ }));
  expect(screen.getByRole('button', { name: /少冰/ })).toHaveAttribute('aria-pressed', 'false');
  fireEvent.click(screen.getByRole('button', { name: /Kao/ }));
  fireEvent.click(screen.getByRole('button', { name: /热 HOT/ }));
  expect(screen.queryByRole('button', { name: /去冰/ })).not.toBeInTheDocument();
  fireEvent.click(screen.getByRole('button', { name: '加入草稿 · RM 2.30' }));
  expect(new Set(add.mock.calls[0][1])).toEqual(new Set([1, 5, 8]));
  fireEvent.click(screen.getByRole('button', { name: /冰 ICED/ }));
  expect(screen.getByRole('button', { name: /去冰/ })).toHaveAttribute('aria-pressed', 'false');
});
