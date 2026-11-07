import { act, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { afterEach, expect, it, vi } from 'vitest';
import Session from './Session';
import { useAuth } from '../stores/auth';

const apiMock = vi.hoisted(() => vi.fn());
vi.mock('../services/api', () => ({ api: apiMock, requestKey: () => 'test-request-identity', clearKey: vi.fn() }));
afterEach(() => { useAuth.getState().signOut(); apiMock.mockReset(); });

it('keeps the next selected dish open when the previous add finishes saving', async () => {
  let finishAdd!: (value: unknown) => void;
  const addPromise = new Promise((resolve) => { finishAdd = resolve; });
  const bill = { session_id: 1, table: 'T01', status: 'OCCUPIED', items: [], total: 0, item_count: 0, has_drafts: true };
  const batches = [{ id: 1, status: 'DRAFT', user_id: 1, items: [] }];
  const menu = [
    { id: 1, name: '云吞面', base_price: 800, groups: [] },
    { id: 2, name: '面粉粿', base_price: 800, groups: [{ id: 2, name: '鸡蛋', minimum: 1, maximum: 1, options: [
      { id: 3, name: '不加蛋', price: 0, is_default: true }, { id: 4, name: '加蛋', price: 100, is_default: false },
    ] }] },
  ];
  apiMock.mockImplementation((path: string, method: string) => {
    if (path === '/order-batches/1/items' && method === 'POST') return addPromise;
    if (path.endsWith('/bill')) return Promise.resolve(bill);
    if (path.endsWith('/orders')) return Promise.resolve(batches);
    if (path === '/menu') return Promise.resolve(menu);
    throw new Error(`Unexpected API ${method} ${path}`);
  });
  useAuth.getState().signIn('test-token', { id: 1, name: 'test-owner', role: 'ADMIN' });
  const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  const view = render(<QueryClientProvider client={client}><MemoryRouter initialEntries={['/session/1']}><Routes><Route path="/session/:id" element={<Session />} /></Routes></MemoryRouter></QueryClientProvider>);
  fireEvent.click(await screen.findByRole('button', { name: /^云吞面/ }));
  fireEvent.click(screen.getByRole('button', { name: '加入草稿 · RM 8.00' }));
  await waitFor(() => expect(apiMock).toHaveBeenCalledWith('/order-batches/1/items', 'POST', expect.anything(), 'test-request-identity'));
  fireEvent.click(screen.getByRole('button', { name: /^面粉粿/ }));
  expect(screen.getByRole('heading', { name: '面粉粿' })).toBeVisible();
  await act(async () => { finishAdd({ id: 10 }); await addPromise; });
  await waitFor(() => expect(screen.getByRole('button', { name: '加入草稿 · RM 8.00' })).toBeEnabled());
  expect(screen.getByRole('heading', { name: '面粉粿' })).toBeVisible();
  expect(screen.getByRole('button', { name: /加蛋.*RM 1.00/ })).toBeVisible();
  view.unmount();
  client.clear();
});

it('smoothly scrolls to the updated item list on every category click, including the selected category', async () => {
  const scroll = vi.fn();
  const original = Object.getOwnPropertyDescriptor(HTMLElement.prototype, 'scrollIntoView');
  Object.defineProperty(HTMLElement.prototype, 'scrollIntoView', {configurable:true,value:scroll});
  apiMock.mockImplementation((path:string)=>Promise.resolve(path.endsWith('/bill')
    ? {session_id:1,table:'T01',status:'OCCUPIED',items:[],total:0,item_count:0,has_drafts:false}
    : path.endsWith('/orders') ? [] : [
      {id:1,name:'云吞面',base_price:800,category_code:'MAINS',groups:[]},
      {id:2,name:'Milo',base_price:300,category_code:'DRINKS',groups:[]},
    ]));
  useAuth.getState().signIn('token',{id:1,name:'owner',role:'ADMIN'});
  const client = new QueryClient({defaultOptions:{queries:{retry:false}}});
  const view = render(<QueryClientProvider client={client}><MemoryRouter initialEntries={['/session/1']}>
    <Routes><Route path="/session/:id" element={<Session/>}/></Routes></MemoryRouter></QueryClientProvider>);
  try {
    const mains=await screen.findByRole('button',{name:/主食/});
    expect(scroll).not.toHaveBeenCalled();
    for (const category of [screen.getByRole('button',{name:/饮料/}),mains,mains]) {
      fireEvent.click(category);
      expect(scroll).toHaveBeenLastCalledWith({behavior:'smooth',block:'start'});
      expect(scroll.mock.contexts.at(-1)).toBe(screen.getByRole('region',{name:'餐点选择'}));
    }
    expect(scroll).toHaveBeenCalledTimes(3);
    expect(screen.getByRole('button',{name:/^云吞面 RM/})).toBeVisible();
  } finally {
    view.unmount();client.clear();
    if(original)Object.defineProperty(HTMLElement.prototype,'scrollIntoView',original);
    else Reflect.deleteProperty(HTMLElement.prototype,'scrollIntoView');
  }
});
