import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { afterEach, expect, it, vi } from 'vitest';
import Tables from './Tables';
import Session from './Session';
import { useAuth } from '../stores/auth';

const apiMock = vi.hoisted(() => vi.fn());
vi.mock('../services/api', () => ({ api: apiMock, requestKey: () => 'test-key', clearKey: vi.fn() }));
afterEach(() => { apiMock.mockReset(); useAuth.getState().signOut(); });

it('shows the shared ordering badge without changing table availability and hides it after submission',async()=>{
  let pending=true;
  apiMock.mockImplementation(()=>Promise.resolve([{id:1,name:'T01',status:'AVAILABLE',session_id:1,total:0,item_count:0,ordering_in_progress:pending}]));
  const client=new QueryClient({defaultOptions:{queries:{retry:false}}});
  const view=render(<QueryClientProvider client={client}><MemoryRouter><Tables/></MemoryRouter></QueryClientProvider>);
  expect(await screen.findByText('下单中')).toHaveClass('table-ordering-note');
  expect(screen.getByRole('button',{name:/^T01/})).toHaveClass('AVAILABLE');
  pending=false;
  await client.invalidateQueries({queryKey:['tables']});
  await waitFor(()=>expect(screen.queryByText('下单中')).not.toBeInTheDocument());
  view.unmount();client.clear();
});

it('shows waiting takeaway and green paid labels without changing the underlying order state',async()=>{
  let packed=true;
  apiMock.mockImplementation(()=>Promise.resolve([{id:1,name:'T01',status:'OCCUPIED',session_id:1,total:800,item_count:1,
    all_takeaway:packed,prepaid_label_status:packed?'ALL':'PARTIAL'}]));
  const client=new QueryClient({defaultOptions:{queries:{retry:false}}});
  const view=render(<QueryClientProvider client={client}><MemoryRouter><Tables/></MemoryRouter></QueryClientProvider>);
  expect(await screen.findByText('等待打包')).toBeVisible();
  expect(screen.getByText('已付款')).toHaveClass('table-paid-note');
  expect(screen.getByRole('button',{name:/^T01/})).toHaveClass('OCCUPIED');
  packed=false;
  await client.invalidateQueries({queryKey:['tables']});
  expect(await screen.findByText('用餐中')).toBeVisible();
  expect(screen.getByText('部分已付款')).toHaveClass('table-paid-note');
  view.unmount();client.clear();
});

it('keeps overdue tables red and stops blinking after acknowledgement without opening the table', async () => {
  let acknowledged: string | null = null;
  apiMock.mockImplementation((path: string) => {
    if (path === '/tables') return Promise.resolve([
      { id: 1, name: 'T01', status: 'OCCUPIED', session_id: 1, first_order_at: '2026-11-07T04:00:00Z', total: 800,
        item_count: 1, wait_alert_due: true, wait_alert_acknowledged_at: acknowledged },
      { id: 2, name: 'T02', status: 'AVAILABLE', total: 0, item_count: 0, session_id: null, wait_alert_due: false },
    ]);
    if (path === '/table-sessions/1/acknowledge-wait') {
      acknowledged = '2026-11-07T04:46:00Z';
      return Promise.resolve({ session_id: 1, wait_alert_acknowledged_at: acknowledged });
    }
    throw new Error(path);
  });
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const view = render(<QueryClientProvider client={client}><MemoryRouter><Tables /></MemoryRouter></QueryClientProvider>);
  const card = (await screen.findByRole('button', { name: /^T01 用餐中/ })).closest('.table-card')!;
  expect(card).toHaveClass('wait-alert', 'needs-attention');
  expect(card.querySelector('.elapsed')).toHaveClass('overdue');
  expect(screen.getByRole('button', { name: /^T02 / }).closest('.table-card')).not.toHaveClass('wait-alert');
  fireEvent.click(within(card as HTMLElement).getByRole('button', { name: 'T01 已留意，停止闪烁' }));
  await waitFor(() => expect(card).not.toHaveClass('needs-attention'));
  expect(card).toHaveClass('wait-alert');
  expect(within(card as HTMLElement).getByLabelText('已留意，已停止闪烁')).toBeVisible();
  expect(apiMock).toHaveBeenCalledWith('/table-sessions/1/acknowledge-wait', 'POST');
  expect(apiMock.mock.calls.some(([path]) => path.endsWith('/open'))).toBe(false);
  view.unmount(); client.clear();
});

it('keeps blinking when acknowledgement cannot reach the server', async () => {
  apiMock.mockImplementation((path: string) => path === '/tables' ? Promise.resolve([
    { id: 1, name: 'T01', status: 'OCCUPIED', session_id: 1, total: 800, item_count: 1, wait_alert_due: true },
  ]) : Promise.reject(new Error('连接失败')));
  const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  const view = render(<QueryClientProvider client={client}><MemoryRouter><Tables /></MemoryRouter></QueryClientProvider>);
  fireEvent.click(await screen.findByRole('button', { name: 'T01 已留意，停止闪烁' }));
  expect(await screen.findByText('连接失败')).toBeVisible();
  expect(screen.getByRole('button', { name: /^T01 用餐中/ }).closest('.table-card')).toHaveClass('needs-attention');
  view.unmount(); client.clear();
});

it('places whole-table remarks after ordering, submitted bills and other staff drafts', async () => {
  apiMock.mockImplementation((path: string) => {
    if (path.endsWith('/bill')) return Promise.resolve({ session_id: 1, table: 'T01', status: 'OCCUPIED', items: [],
      total: 0, item_count: 0, has_drafts: true, metadata_revision: 1, table_notes: '先上饮料' });
    if (path.endsWith('/orders')) return Promise.resolve([{ id: 2, status: 'DRAFT', user_id: 2, items: [] }]);
    if (path === '/menu') return Promise.resolve([]);
    throw new Error(path);
  });
  useAuth.getState().signIn('token', { id: 1, name: 'owner', role: 'ADMIN' });
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const view = render(<QueryClientProvider client={client}><MemoryRouter initialEntries={['/session/1']}>
    <Routes><Route path="/session/:id" element={<Session />} /></Routes></MemoryRouter></QueryClientProvider>);
  const notes = await screen.findByLabelText('整桌备注（所有轮次）');
  const section = notes.closest('section')!;
  expect(section.nextElementSibling).toBeNull();
  expect(notes).toHaveValue('先上饮料');
  view.unmount(); client.clear();
});
