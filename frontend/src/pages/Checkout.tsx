import { useState, useEffect } from 'react';
import { Link, useParams, useNavigate } from 'react-router-dom';
import { useMutation, useQuery } from '@tanstack/react-query';
import { api, requestKey } from '../services/api';
import type { Bill, Payment } from '../services/types';
import { money, parseSen } from '../utils/format';
import { Lines, ErrorBox, Loading } from '../components/Common';
import { useUI } from '../stores/ui';

export default function Checkout() {
  const { id } = useParams();
  const navigate = useNavigate();
  const [method, setMethod] = useState('QR');
  const [received, setReceived] = useState('');
  const [discard, setDiscard] = useState(false);
  const bill = useQuery({
    queryKey: ['bill', id],
    queryFn: () => api<Bill>(`/table-sessions/${id}/bill`),
    refetchInterval: 4000,
  });
  const sen = parseSen(received);
  const total = bill.data?.total ?? 0;
  const hasDrafts = bill.data?.has_drafts ?? false;
  useEffect(() => {
    setDiscard(false);
  }, [id, total, hasDrafts, bill.data?.status]);
  const pay = useMutation({
    mutationFn: () => {
      const payload = {
        method,
        received: method === 'CASH' ? (sen ?? (total === 0 ? 0 : null)) : total,
        expected_total: total,
        discard_drafts: discard,
      };
      // An uncertain response retains the same identity after retry or reload.
      const key = requestKey(`pay:${id}:${JSON.stringify(payload)}`);
      return api<Payment>(`/table-sessions/${id}/payments`, 'POST', payload, key);
    },
    onSuccess: (payment) => {
      useUI.getState().setNotice(
        `收款完成 · ${money(payment.total)} · 找零 ${money(payment.change)}`,
      );
      navigate(`/receipts/${payment.id}`);
    },
  });
  const resume = useMutation({
    mutationFn: () => api(`/table-sessions/${id}/resume`, 'POST'),
    onSuccess: () => navigate(`/session/${id}`),
  });

  if (bill.isPending) return <><Loading /><ErrorBox error={bill.error} /></>;
  const blocked = bill.isError || pay.isPending || !bill.data?.item_count || bill.data?.status !== 'PAYMENT_PENDING'
    || (bill.data?.has_drafts && !discard)
    || (method === 'CASH' && ((total > 0 && sen === null) || (sen !== null && sen < total)));

  return (
    <>
      <Link to={`/session/${id}`} className="back">← 查看订单</Link>
      <h1>{bill.data?.table} · 收款</h1>
      <ErrorBox error={bill.error || pay.error || resume.error} />
      {bill.data?.has_prepaid_label && <p className="warning">部分订单已手动标记先付款，请核实已收款项，避免重复收款。此处仍需完成收银记录。</p>}
      {bill.data?.status === 'OCCUPIED' && <p className="notice" role="status">
        此桌已恢复点餐，请返回订单页面重新核对账单并开始结账。
      </p>}
      <section className="card stack">
        <Lines items={bill.data?.items ?? []} />
        {bill.data?.table_notes && <p className="order-notes">整桌备注：{bill.data.table_notes}</p>}
        {bill.data?.order_notes?.map((note) => <p className="order-notes" key={note.batch_id}>订单 #{note.batch_id} 备注：{note.notes}</p>)}
        <div className="row spread"><h2>应收总额</h2><h1>{money(total)}</h1></div>
        <div className="option-grid">
          {[['CASH', '现金'], ['QR', '二维码'], ['OTHER', '其他']].map(([value, name]) => (
            <button key={value} className={method === value ? 'selected' : ''}
              aria-pressed={method === value} onClick={() => setMethod(value)}>{name}</button>
          ))}
        </div>
        {method === 'CASH' ? <>
          <label>
            收到现金 (RM)
            <input inputMode="decimal" value={received} placeholder="50.00"
              onChange={(event) => setReceived(event.target.value)} />
          </label>
          <div className="row spread">
            <strong>应找零</strong>
            <strong>{sen !== null && sen >= total ? money(sen - total) : '金额不足或格式有误'}</strong>
          </div>
        </> : <p className="muted">请核实款项到账后点击收款。系统会直接完成收款、清台并生成收据。</p>}
        {bill.data?.has_drafts && (
          <label className="check warning">
            <input type="checkbox" checked={discard}
              onChange={(event) => setDiscard(event.target.checked)} />
            存在未下单草稿。我确认丢弃本桌全部草稿后收款。
          </label>
        )}
        <button type="button" className="primary" disabled={!!blocked} onClick={() => pay.mutate()}>
          {pay.isPending ? '正在收款…' : '确认收款并清台'}
        </button>
        <button onClick={() => resume.mutate()} disabled={resume.isPending || pay.isPending}>返回继续加单</button>
      </section>
    </>
  );
}
