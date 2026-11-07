import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter } from 'react-router-dom';
import { expect, it, vi } from 'vitest';
import History from './History';

const mockApi=vi.hoisted(()=>vi.fn());
vi.mock('../services/api',()=>({api:mockApi}));

it('uses the server business day, follows its noon rollover, and preserves a chosen historical day',async()=>{
  let serverDay='2026-11-07';
  mockApi.mockImplementation((path:string)=>{
    if(path.startsWith('/reports/transactions'))return Promise.resolve([]);
    const requested=new URLSearchParams(path.split('?')[1]).get('day');
    return Promise.resolve({date:requested??serverDay,total:800,methods:{CASH:0,QR:800,OTHER:0}});
  });
  const client=new QueryClient({defaultOptions:{queries:{retry:false}}});
  const view=render(<QueryClientProvider client={client}><MemoryRouter><History/></MemoryRouter></QueryClientProvider>);
  try {
    await waitFor(()=>expect(screen.getByLabelText('营业日期')).toHaveValue('2026-11-07'));
    expect(mockApi).toHaveBeenCalledWith('/reports/daily-sales');
    await waitFor(()=>expect(mockApi).toHaveBeenCalledWith('/reports/transactions?day=2026-11-07'));
    expect(screen.getByText(/中午 12:00/)).toBeVisible();
    serverDay='2026-11-08';
    await client.invalidateQueries({queryKey:['sales']});
    await waitFor(()=>expect(screen.getByLabelText('营业日期')).toHaveValue('2026-11-08'));
    await waitFor(()=>expect(mockApi).toHaveBeenCalledWith('/reports/transactions?day=2026-11-08'));
    fireEvent.change(screen.getByLabelText('营业日期'),{target:{value:'2026-11-06'}});
    await waitFor(()=>expect(mockApi).toHaveBeenCalledWith('/reports/daily-sales?day=2026-11-06'));
    serverDay='2026-11-09';
    await client.invalidateQueries({queryKey:['sales']});
    expect(screen.getByLabelText('营业日期')).toHaveValue('2026-11-06');
  } finally {view.unmount();client.clear();mockApi.mockReset();}
});
