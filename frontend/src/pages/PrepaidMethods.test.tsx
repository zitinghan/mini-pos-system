import { fireEvent,render,screen,waitFor,within } from '@testing-library/react';
import { QueryClient,QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter,Routes,Route } from 'react-router-dom';
import { afterEach,expect,it,vi } from 'vitest';
import Session from './Session';
import {useAuth} from '../stores/auth';

const mockApi=vi.hoisted(()=>vi.fn());
vi.mock('../services/api',()=>({api:mockApi,requestKey:()=> 'test-request',clearKey:vi.fn()}));
afterEach(()=>{mockApi.mockReset();useAuth.getState().signOut();});

async function setup(paid=false,method:string|null=null){
  let batch={id:1,status:'SUBMITTED',user_id:1,items:[],prepaid_label:paid,prepaid_method:method,info_revision:1,notes:''};
  mockApi.mockImplementation((path:string,http:string,payload:any)=>{
    if(path.endsWith('/details')&&http==='PATCH'){
      batch={...batch,...payload,info_revision:batch.info_revision+1};return Promise.resolve(batch);
    }
    if(path.endsWith('/orders'))return Promise.resolve([batch]);
    if(path.endsWith('/bill'))return Promise.resolve({session_id:1,table:'T01',status:'OCCUPIED',items:[],total:800,item_count:1,has_drafts:false});
    if(path==='/menu')return Promise.resolve([]);
    throw new Error(path);
  });
  useAuth.getState().signIn('token',{id:1,name:'staff',role:'STAFF'});
  const client=new QueryClient({defaultOptions:{queries:{retry:false},mutations:{retry:false}}});
  const view=render(<QueryClientProvider client={client}><MemoryRouter initialEntries={['/session/1']}>
    <Routes><Route path="/session/:id" element={<Session/>}/></Routes></MemoryRouter></QueryClientProvider>);
  fireEvent.click(await screen.findByRole('button',{name:'修改本轮备注 / 付款标记'}));
  return {client,view,dialog:screen.getByRole('dialog',{name:'修改整单备注'})};
}

it('lets staff mark a submitted round paid by cash and later change it to QR',async()=>{
  const {client,view,dialog}=await setup();
  fireEvent.click(within(dialog).getByRole('checkbox',{name:'本轮已付款（仅手动标记）'}));
  expect(within(dialog).getByLabelText('本轮付款方式')).toHaveValue('QR');
  fireEvent.change(within(dialog).getByLabelText('本轮付款方式'),{target:{value:'CASH'}});
  fireEvent.click(within(dialog).getByRole('button',{name:'保存备注 / 标记'}));
  await waitFor(()=>expect(screen.queryByRole('dialog')).not.toBeInTheDocument());
  expect(await screen.findByText('· 现金')).toBeVisible();
  fireEvent.click(screen.getByRole('button',{name:'修改本轮备注 / 付款标记'}));
  const editor=screen.getByRole('dialog',{name:'修改整单备注'});
  expect(within(editor).getByLabelText('本轮付款方式')).toHaveValue('CASH');
  fireEvent.change(within(editor).getByLabelText('本轮付款方式'),{target:{value:'QR'}});
  fireEvent.click(within(editor).getByRole('button',{name:'保存备注 / 标记'}));
  await waitFor(()=>expect(screen.queryByRole('dialog')).not.toBeInTheDocument());
  expect(await screen.findByText('· 二维码')).toBeVisible();
  view.unmount();client.clear();
});

it('does not invent a method for an older paid label with unknown method',async()=>{
  const {client,view,dialog}=await setup(true);
  expect(within(dialog).getByLabelText('本轮付款方式')).toHaveValue('');
  expect(within(dialog).getByRole('option',{name:'未记录（可选择）'})).toBeInTheDocument();
  view.unmount();client.clear();
});
