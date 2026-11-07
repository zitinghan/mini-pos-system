import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, expect, it, vi } from 'vitest';
import Orders from './Orders';
import { useAuth } from '../stores/auth';

const apiMock = vi.hoisted(() => vi.fn());
vi.mock('../services/api', () => ({ api: apiMock, previewJob: vi.fn(), requestKey: vi.fn(), clearKey: vi.fn() }));
afterEach(() => { useAuth.getState().signOut(); apiMock.mockReset(); });

it('shows unfinished sent orders with table/status and loads completed records only when expanded', async () => {
  const job = { id: 1, batch_id: 10, table: 'T05', session_id: 1, session_status: 'OCCUPIED', completed: false,
    status: 'SENT', routing_group: 'KITCHEN', attempts: 1, reprint: false, error: null, preview: null, created_at: '2026-11-07T04:00:00+00:00' };
  let paid = false;
  apiMock.mockImplementation((path: string) => {
    if (path === '/tables') return Promise.resolve([]);
    if (path.endsWith('completed=false')) return Promise.resolve(paid ? [] : [job]);
    if (path.endsWith('completed=true')) return Promise.resolve([{ ...job, id: 2, table: 'T06', completed: true,
      session_status: 'PAID', status: 'FAILED', error: 'Connection refused' }]);
    throw new Error(`Unexpected API: ${path}`);
  });
  useAuth.getState().signIn('test-token', { id: 1, name: 'owner', role: 'ADMIN' });
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const view = render(<QueryClientProvider client={client}><MemoryRouter><Orders /></MemoryRouter></QueryClientProvider>);
  expect(await screen.findByRole('heading', { name: '桌号 T05' })).toBeVisible();
  expect(screen.getByText('未完成 · 用餐中')).toBeVisible();
  expect(screen.getByText('已发送至打印机')).toBeVisible();
  expect(apiMock).not.toHaveBeenCalledWith('/print-jobs?completed=true');
  const expand = screen.getByRole('button', { name: '展开已完成订单' });
  expect(expand).toHaveAttribute('aria-expanded', 'false');
  fireEvent.click(expand);
  const history = await screen.findByRole('region', { name: '已完成订单' });
  expect(await within(history).findByRole('heading', { name: '桌号 T06' })).toBeVisible();
  expect(within(history).getByText('已完成 · 已付款')).toBeVisible();
  expect(within(history).getByText('打印失败')).toBeVisible();
  fireEvent.click(screen.getByRole('button', { name: '收起已完成订单' }));
  expect(screen.queryByRole('heading', { name: '桌号 T06' })).not.toBeInTheDocument();
  paid = true;
  await client.invalidateQueries({ queryKey: ['print-jobs', 'active'] });
  await waitFor(() => expect(screen.queryByRole('heading', { name: '桌号 T05' })).not.toBeInTheDocument());
  expect(screen.getByText('暂无未完成订单。')).toBeVisible();
  view.unmount(); client.clear();
});
