import { useState, useEffect } from 'react';
import { Link, useParams, useNavigate } from 'react-router-dom';
import { useMutation, useQuery } from '@tanstack/react-query';
import { api, requestKey } from '../services/api';
import type { Bill, Payment } from '../services/types';
import { money, parseSen } from '../utils/format';
import { Lines, ErrorBox, Loading, ConfirmButton } from '../components/Common';
import { useUI } from '../stores/ui';

export default function Checkout() {
  const { id } = useParams();
  const navigate = useNavigate();
  const [method, setMethod] = useState('CASH');
  const [received, setReceived] = useState('');
  const [discard, setDiscard] = useState(false);
  const [verified, setVerified] = useState(false);
  const bill = useQuery({
    queryKey: ['bill', id],
    queryFn: () => api<Bill>(`/table-sessions/${id}/bill`),
    refetchInterval: 4000,
  });
  const sen = parseSen(received);
  const total = bill.data?.total ?? 0;
  const hasDrafts = bill.data?.has_drafts ?? false;
  useEffect(() => {
    setVerified(false);
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
      navigate('/');
    },
  });
  const resume = useMutation({
    mutationFn: () => api(`/table-sessions/${id}/resume`, 'POST'),
    onSuccess: () => navigate(`/session/${id}`),
  });

  if (bill.isPending) return <><Loading /><ErrorBox error={bill.error} /></>;
  const blocked = bill.isError || pay.isPending || !bill.data?.item_count || bill.data?.status !== 'PAYMENT_PENDING'
    || (bill.data?.has_drafts && !discard)
    || (method === 'CASH' ? (total > 0 && sen === null) || (sen !== null && sen < total) : total > 0 && !verified);

  return (
    <>
      <Link to={`/session/${id}`} className="back">← 查看订单</Link>
      <h1>{bill.data?.table} · 收款</h1>
      <ErrorBox error={bill.error || pay.error || resume.error} />
      {bill.data?.status === 'OCCUPIED' && <p className="notice" role="status">
        此桌已恢复点餐，请返回订单页面重新核对账单并开始结账。
      </p>}
      <section className="card stack">
        <Lines items={bill.data?.items ?? []} />
        <div className="row spread"><h2>应收总额</h2><h1>{money(total)}</h1></div>
        <div className="option-grid">
          {[['CASH', '现金'], ['QR', '二维码'], ['OTHER', '其他']].map(([value, name]) => (
            <button key={value} className={method === value ? 'selected' : ''}
              onClick={() => { setMethod(value); setVerified(false); }}>{name}</button>
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
        </> : (
          <label className="check">
            <input type="checkbox" checked={verified}
              onChange={(event) => setVerified(event.target.checked)} />
            我已人工核实款项到账（系统不会自动验证）
          </label>
        )}
        {bill.data?.has_drafts && (
          <label className="check warning">
            <input type="checkbox" checked={discard}
              onChange={(event) => setDiscard(event.target.checked)} />
            存在未下单草稿。我确认丢弃本桌全部草稿后收款。
          </label>
        )}
        <ConfirmButton key={`${id}:${total}:${hasDrafts}:${method}`} disabled={!!blocked} onConfirm={() => pay.mutate()}>
          {pay.isPending ? '正在收款…' : '确认收款并清台'}
        </ConfirmButton>
        <button onClick={() => resume.mutate()} disabled={resume.isPending || pay.isPending}>返回继续加单</button>
      </section>
    </>
  );
}
