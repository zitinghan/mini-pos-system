import { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { api, previewJob, requestKey, clearKey } from '../services/api';
import type { PrintJob, Table } from '../services/types';
import { label, translateError } from '../utils/i18n';
import { localTime, money } from '../utils/format';
import { useAuth } from '../stores/auth';
import { ErrorBox, ConfirmButton, Loading } from '../components/Common';

export default function Orders() {
  const admin = useAuth((state) => state.user?.role === 'ADMIN');
  const client = useQueryClient();
  const [image, setImage] = useState<string | null>(null);
  const [error, setError] = useState<unknown>(null);
  const jobs = useQuery({
    queryKey: ['print-jobs'],
    queryFn: () => api<PrintJob[]>('/print-jobs'),
    refetchInterval: 4000,
  });
  const tables = useQuery({
    queryKey: ['tables'],
    queryFn: () => api<Table[]>('/tables'),
    refetchInterval: 4000,
  });
  const retry = useMutation({
    mutationFn: async (id: number) => {
      const scope = `reprint:${id}`;
      const job = await api<PrintJob>(`/print-jobs/${id}/retry`, 'POST', undefined, requestKey(scope));
      clearKey(scope);
      return job;
    },
    onSuccess: () => {
      setError(null);
      void client.invalidateQueries({ queryKey: ['print-jobs'] });
    },
    onError: setError,
  });

  useEffect(() => () => { if (image) URL.revokeObjectURL(image); }, [image]);

  return (
    <>
      <h1>当前订单</h1>
      <div className="active-tables">
        {tables.data?.filter((table) => table.session_id).map((table) => (
          <Link className="pill" key={table.id} to={`/session/${table.session_id}`}>
            {table.name} · {money(table.total)}
          </Link>
        ))}
      </div>
      <h2>厨房 / 饮料打印记录</h2>
      <p className="muted">“已发送”代表数据已送出，请留意厨房是否实际出纸。重复打印会标记“重印”。</p>
      <ErrorBox error={jobs.error || tables.error || error} />
      {jobs.isPending && <Loading />}
      {jobs.data?.map((job) => (
        <section className="card stack" key={job.id}>
          <div className="row spread">
            <strong>{job.batch_id ? `订单 #${job.batch_id}` : '测试单'} / 任务 #{job.id}</strong>
            <span className={`print-status ${job.status}`}>{label(job.status)}</span>
          </div>
          <small>{localTime(job.created_at)} · {job.routing_group === 'BEVERAGE' ? '饮料' : job.routing_group === 'KITCHEN' ? '厨房' : '厨房 / 饮料'} · 尝试 {job.attempts} 次 {job.reprint ? '· 重印' : ''}</small>
          {job.error && <p className="error">{translateError(job.error)}</p>}
          <div className="row">
            {job.preview && (
              <button onClick={() => { previewJob(job.id).then(setImage).catch(setError); }}>
                查看厨房单
              </button>
            )}
            {admin && !['PENDING', 'SENDING'].includes(job.status) && (
              <ConfirmButton disabled={retry.isPending} onConfirm={() => retry.mutate(job.id)}>
                核实厨房后重印
              </ConfirmButton>
            )}
          </div>
        </section>
      ))}
      {image && (
        <div className="modal" role="dialog" aria-modal="true" aria-label="厨房单预览">
          <div className="stack">
            <button onClick={() => setImage(null)}>关闭预览</button>
            <img className="ticket-preview" src={image} alt="厨房订单，无价格" />
          </div>
        </div>
      )}
    </>
  );
}
