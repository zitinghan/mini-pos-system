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
  const [receiptImage, setReceiptImage] = useState(false);
  const [error, setError] = useState<unknown>(null);
  const [showCompleted, setShowCompleted] = useState(false);
  const jobs = useQuery({
    queryKey: ['print-jobs', 'active'],
    queryFn: () => api<PrintJob[]>('/print-jobs?completed=false'),
    refetchInterval: 4000,
  });
  const completed = useQuery({
    queryKey: ['print-jobs', 'completed'],
    queryFn: () => api<PrintJob[]>('/print-jobs?completed=true'),
    enabled: showCompleted,
    refetchInterval: showCompleted ? 4000 : false,
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

  const orderCard = (job: PrintJob) => (
    <section className="card stack order-card" key={job.id}>
      <div className="row spread">
        <h2>桌号 {job.table || '—'}</h2>
        <span className="pill">{job.completed ? '已完成' : '未完成'}{job.session_status ? ` · ${label(job.session_status)}` : ' · 测试单'}</span>
      </div>
      <div className="row spread">
        <strong>{job.payment_id ? `收据 R${String(job.payment_id).padStart(6, '0')}` : job.batch_id ? `订单 #${job.batch_id}` : job.session_id ? '整桌通知' : '测试单'} / 任务 #{job.id}</strong>
        <span className={`print-status ${job.status}`}>{label(job.status)}</span>
      </div>
      <small>{localTime(job.created_at)} · {label(job.routing_group ?? 'COMBINED')} · 尝试 {job.attempts} 次 {job.reprint ? '· 重印' : ''}</small>
      {job.order_type === 'UPDATE' && <strong className="warning">更改单 · 请用新内容替换旧内容</strong>}
      {job.order_type === 'CANCEL' && <strong className="warning">取消单 · 停止制作 / 不要出餐</strong>}
      {job.order_type === 'NOTE' && <strong className="notice">备注 / 标记更新 · 不新增餐点</strong>}
      {job.prepaid_label && <strong className="pill">已付款（手动标记）</strong>}
      {job.reason && <p>取消原因：{job.reason}</p>}
      {job.table_notes && <p className="order-notes">整桌备注：{job.table_notes}</p>}
      {job.notes && <p className="order-notes">整单备注：{job.notes}</p>}
      {job.error && <p className="error">{translateError(job.error)}</p>}
      <div className="row">
        {job.session_id && ['OCCUPIED','PAYMENT_PENDING'].includes(job.session_status ?? '') && <Link className="back" to={`/session/${job.session_id}`}>打开此桌</Link>}
        {job.preview && <button onClick={() => { setReceiptImage(job.document_type === 'RECEIPT'); previewJob(job.id).then(setImage).catch(setError); }}>
          {job.document_type === 'RECEIPT' ? '查看收据' : '查看厨房单'}
        </button>}
        {job.payment_id && <Link className="back" to={`/receipts/${job.payment_id}`}>打开付款收据</Link>}
        {admin && !['PENDING', 'SENDING'].includes(job.status) && <ConfirmButton disabled={retry.isPending} onConfirm={() => retry.mutate(job.id)}>
          核实{job.payment_id ? '收银' : '厨房'}后重印
        </ConfirmButton>}
      </div>
    </section>
  );

  return (
    <>
      <h1>当前订单</h1>
      <div className="active-tables">
        {tables.data?.filter((table) => table.session_id && table.status !== 'AVAILABLE').map((table) => (
          <Link className="pill" key={table.id} to={`/session/${table.session_id}`}>
            {table.name} · {money(table.total)}
          </Link>
        ))}
      </div>
      <h2>未完成订单{jobs.data ? `（${jobs.data.length}）` : ''}</h2>
      <p className="muted">付款并清台后归入已完成订单。“已发送”仅代表打印数据已送出，请核实实际出纸。重印会保留标记。</p>
      <ErrorBox error={jobs.error || tables.error || error} />
      {jobs.isPending && <Loading />}
      {jobs.data?.length === 0 && <p className="muted">暂无未完成订单。</p>}
      {jobs.data?.map(orderCard)}
      <button type="button" aria-expanded={showCompleted} aria-controls="completed-orders" onClick={() => setShowCompleted((value) => !value)}>
        {showCompleted ? '收起已完成订单' : '展开已完成订单'}
      </button>
      {showCompleted && <section id="completed-orders" aria-label="已完成订单">
        <h2>已完成订单</h2><small>最近 100 条记录，可查看打印状态及重印。</small>
        {completed.isPending && <Loading />}
        <ErrorBox error={completed.error} />
        {completed.data?.length === 0 && <p className="muted">暂无已完成订单。</p>}
        {completed.data?.map(orderCard)}
      </section>}
      {image && (
        <div className="modal" role="dialog" aria-modal="true" aria-label="厨房单预览"
          onClick={(event) => { if (event.target === event.currentTarget) setImage(null); }}>
          <div className="stack">
            <button onClick={() => setImage(null)}>关闭预览</button>
            <img className="ticket-preview" src={image} alt={receiptImage ? '客户收据及付款金额' : '厨房订单，无价格'} />
          </div>
        </div>
      )}
    </>
  );
}
