import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useNavigate } from 'react-router-dom';
import { api } from '../services/api';
import type { Table } from '../services/types';
import { money, elapsed } from '../utils/format';
import { label } from '../utils/i18n';
import { ErrorBox, Loading } from '../components/Common';

export default function Tables() {
  const navigate = useNavigate();
  const client = useQueryClient();
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

  return (
    <>
      <div className="page-title">
        <div><p className="eyebrow">{query.data ? `今日服务 · ${query.data.length} 张桌台` : '正在加载桌台'}</p><h1>选择桌台</h1></div>
        <span className="pill">每 4 秒更新</span>
      </div>
      <div className="legend"><span>● 空桌</span><span>● 用餐中</span><span>● 待结账</span></div>
      <ErrorBox error={query.error || open.error} />
      {query.isPending && <Loading />}
      <div className="table-grid">
        {query.data?.map((table) => (
          <button className={`table-card ${table.status}`} key={table.id}
            disabled={open.isPending}
            onClick={() => table.session_id
              ? navigate(`/session/${table.session_id}`)
              : open.mutate(table.id)}>
            <span className="table-name">{table.name}</span>
            <span className="status">{label(table.status)}</span>
            <strong>{money(table.total)}</strong>
            <small>{table.item_count} 份 · {table.first_order_at ? elapsed(table.first_order_at) : '尚未下单'}</small>
          </button>
        ))}
      </div>
    </>
  );
}
