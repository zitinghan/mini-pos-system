import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useNavigate } from 'react-router-dom';
import { api } from '../services/api';
import type { Table } from '../services/types';
import { money, elapsed } from '../utils/format';
import { label } from '../utils/i18n';
import { ErrorBox, Loading } from '../components/Common';
import { useAuth } from '../stores/auth';
import TableRecovery from '../components/TableRecovery';

export default function Tables() {
  const navigate = useNavigate();
  const client = useQueryClient();
  const admin = useAuth((state) => state.user?.role === 'ADMIN');
  const query = useQuery({
    queryKey: ['tables'],
    queryFn: () => api<Table[]>('/tables'),
    refetchInterval: 4000,
  });
  const open = useMutation({
    mutationFn: (id: number) => api<{ session_id: number }>(`/tables/${id}/open`, 'POST'),
    onSuccess: (data) => {
      void client.invalidateQueries({ queryKey: ['tables'] });
      navigate(`/session/${data.session_id}`);
    },
  });
  const acknowledge = useMutation({
    mutationFn: (sessionId: number) => api<{ session_id: number; wait_alert_acknowledged_at: string }>(
      `/table-sessions/${sessionId}/acknowledge-wait`, 'POST'),
    onSuccess: (result) => {
      client.setQueryData<Table[]>(['tables'], (tables) => tables?.map((table) => table.session_id === result.session_id
        ? { ...table, wait_alert_acknowledged_at: result.wait_alert_acknowledged_at } : table));
      void client.invalidateQueries({ queryKey: ['tables'] });
    },
  });

  return (
    <>
      <div className="page-title">
        <div><p className="eyebrow">{query.data ? `今日服务 · ${query.data.length} 张桌台` : '正在加载桌台'}</p><h1>选择桌台</h1></div>
        <span className="pill">每 4 秒更新</span>
      </div>
      <div className="legend"><span>● 空桌</span><span>● 用餐中</span><span>● 待结账</span></div>
      {admin && <TableRecovery />}
      <ErrorBox error={query.error || open.error || acknowledge.error} />
      {query.isPending && <Loading />}
      <div className="table-grid">
        {query.data?.map((table) => (
          <div className={`table-card ${table.status}${table.wait_alert_due ? ' wait-alert' : ''}${table.wait_alert_due && !table.wait_alert_acknowledged_at ? ' needs-attention' : ''}`} key={table.id}>
          <button className={`table-open ${table.status}`}
            disabled={open.isPending}
            onClick={() => table.session_id
              ? navigate(`/session/${table.session_id}`)
              : open.mutate(table.id)}>
            <span className="table-name">{table.name}</span>
            <span className="status">{table.status==='OCCUPIED'&&table.all_takeaway?'等待打包':label(table.status)}</span>
            {table.ordering_in_progress && <span className="pill table-ordering-note">下单中</span>}
            {table.prepaid_label_status&&<span className="table-paid-note">{table.prepaid_label_status==='ALL'?'已付款':'部分已付款'}</span>}
            <strong>{money(table.total)}</strong>
            <small>{table.item_count} 份 · <span className={table.wait_alert_due ? 'elapsed overdue' : 'elapsed'}>{table.first_order_at ? elapsed(table.first_order_at) : '尚未下单'}</span></small>
          </button>
          {table.wait_alert_due && (table.wait_alert_acknowledged_at
            ? <small className="attention-acknowledged" aria-label="已留意，已停止闪烁">已留意</small>
            : <button className="attention-ack" aria-label={`${table.name} 已留意，停止闪烁`}
              disabled={acknowledge.isPending} onClick={() => acknowledge.mutate(table.session_id!)}>已留意</button>)}
          </div>
        ))}
      </div>
    </>
  );
}
