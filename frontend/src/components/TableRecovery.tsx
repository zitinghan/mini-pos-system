import { useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useNavigate } from 'react-router-dom';
import { api, requestKey, clearKey } from '../services/api';
import type { Line } from '../services/types';
import { localTime, money } from '../utils/format';
import { Lines, ErrorBox, Loading } from './Common';
import { useUI } from '../stores/ui';

interface ClosedTable {session_id:number;table:string;status:'CANCELLED'|'PAID';closed_at:string|null;items:Line[];
  total:number;payment_total:number|null;table_notes:string;expected_change_token:string;can_restore:boolean;blocked_reason:string}

export default function TableRecovery() {
  const [open, setOpen] = useState(false);
  const [selected, setSelected] = useState<ClosedTable | null>(null);
  const [reason, setReason] = useState('误关桌台');
  const client = useQueryClient();
  const navigate = useNavigate();
  const history = useQuery({queryKey:['table-recovery'],queryFn:()=>api<ClosedTable[]>('/table-recovery'),enabled:open,
    refetchInterval:open ? 4000 : false});
  const restore = useMutation({mutationFn:async () => {
    if (!selected) throw new Error('请选择桌台');
    const payload={expected_change_token:selected.expected_change_token,reason:reason.trim()};
    const scope=`restore:${selected.session_id}:${JSON.stringify(payload)}`;
    const result=await api<{session_id:number;voided_payment_id?:number;print_jobs:{id:number}[]}>(`/table-sessions/${selected.session_id}/restore`,'POST',payload,requestKey(scope));
    clearKey(scope); return result;
  },onSuccess:(result)=>{
    for (const key of ['tables','table-recovery','print-jobs','sales','transactions','receipt']) void client.invalidateQueries({queryKey:[key]});
    setOpen(false); setSelected(null);
    useUI.getState().setNotice(result.voided_payment_id ? '误收款已撤销，原记录保留；桌台已恢复为未付款，未重打制作单。' : result.print_jobs.length ? '桌台已恢复，已通知原档口核对后继续准备，避免重复出餐。' : '桌台及草稿已恢复，没有新增制作单。');
    navigate(`/session/${result.session_id}`);
  }});
  return <>
    <button className="quiet" onClick={()=>{setOpen(true);setSelected(null);restore.reset();}}>恢复误关桌台</button>
    {open && <div className="modal" role="dialog" aria-modal="true" aria-label="恢复误关桌台"
      onClick={(event)=>{if(event.target===event.currentTarget&&!restore.isPending)setOpen(false);}}>
      <div className="card stack"><h2>恢复误关桌台</h2>
        {!selected ? <>
          <p className="muted">最近 100 次关闭记录。桌子正在给另一组客人使用时，不能恢复覆盖。</p>
          <ErrorBox error={history.error}/>{history.isPending&&<Loading/>}
          {history.data?.length===0&&<p>暂无可查看的关闭记录。</p>}
          {history.data?.map((table)=><button key={table.session_id} className="recovery-choice" onClick={()=>{setSelected(table);setReason('误关桌台');restore.reset();}}>
            {table.table} · {table.status==='PAID'?'已收款并清台':'已取消'} · 记录 #{table.session_id}
            <small>{table.closed_at ? localTime(table.closed_at):''} · {money(table.payment_total??table.total)}</small>
            {!table.can_restore&&<small>{table.blocked_reason}</small>}
          </button>)}
        </> : <>
          <h2>{selected.table} · 记录 #{selected.session_id}</h2>
          <Lines items={selected.items.map((item)=>({...item,status:item.status==='DRAFT'?'DRAFT':'SUBMITTED'}))}/>
          {selected.table_notes&&<p className="order-notes">整桌备注：{selected.table_notes}</p>}
          {selected.status==='PAID' ? <p className="warning">将撤销原收款 {money(selected.payment_total??0)}，恢复未付款桌台。原收款和收据保留作废记录，不会重打制作单，也不会向银行或 QR 平台退款。</p>
            :<p>恢复关闭前的餐点、草稿和备注，保留原取消记录，并通知对应档口核对原单继续准备。</p>}
          {!selected.can_restore&&<p className="error">{selected.blocked_reason}</p>}
          <label>恢复原因<input maxLength={240} value={reason} disabled={restore.isPending} onChange={(event)=>setReason(event.target.value)}/></label>
          <ErrorBox error={restore.error}/>
          <button className="primary" disabled={!selected.can_restore||restore.isPending||!reason.trim()} onClick={()=>restore.mutate()}>
            {restore.isPending?'正在恢复…':selected.status==='PAID'?'确认撤销收款并恢复':'确认恢复此桌'}</button>
          <button disabled={restore.isPending} onClick={()=>setSelected(null)}>返回关闭记录</button>
        </>}
        <button disabled={restore.isPending} onClick={()=>setOpen(false)}>关闭</button>
      </div>
    </div>}
  </>;
}
