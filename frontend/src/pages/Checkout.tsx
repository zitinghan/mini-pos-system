import { useState, useEffect } from 'react';
import { Link, useParams, useNavigate } from 'react-router-dom';
import { useMutation, useQuery } from '@tanstack/react-query';
import { api, requestKey } from '../services/api';
import type { Bill, Payment } from '../services/types';
import { money, parseSen } from '../utils/format';
import { label } from '../utils/i18n';
import { Lines, ErrorBox, Loading } from '../components/Common';
import { useUI } from '../stores/ui';

export default function Checkout() {
  const { id } = useParams();
  const navigate = useNavigate();
  const [method, setMethod] = useState('QR');
  const [received, setReceived] = useState('');
  const [discard, setDiscard] = useState(false);
  const [printReceipt, setPrintReceipt] = useState(false);
  const [offer, setOffer] = useState<{ original: number; value: string } | null>(null);
  const [offerReason, setOfferReason] = useState<string | null>(null);
  const bill = useQuery({
    queryKey: ['bill', id],
    queryFn: () => api<Bill>(`/table-sessions/${id}/bill`),
    refetchInterval: 4000,
  });
  const sen = parseSen(received);
  const total = bill.data?.total ?? 0;
  const restoredOffer = bill.data?.recovery_offer;
  const suggestedTotal = restoredOffer?.original_total === total ? restoredOffer.total : total;
  const finalText = offer?.original === total ? offer.value : (suggestedTotal / 100).toFixed(2);
  const currentOfferReason = offerReason ?? restoredOffer?.offer_reason ?? '';
  const finalTotal = parseSen(finalText);
  const validOffer = finalTotal !== null && finalTotal <= total;
  const prepaid = bill.data?.prepaid_total ?? 0;
  const remaining = Math.max(0, (finalTotal ?? total) - prepaid);
  const fullyPaid = prepaid > 0 && remaining === 0;
  const overpaid = validOffer && prepaid > finalTotal!;
  const hasDrafts = bill.data?.has_drafts ?? false;
  useEffect(() => {
    setDiscard(false);
  }, [id, total, hasDrafts, bill.data?.status]);
  const pay = useMutation({
    mutationFn: () => {
      const payload = {
        ...(fullyPaid ? {} : { method }),
        received: fullyPaid ? 0 : method === 'CASH' ? (sen ?? (remaining === 0 ? 0 : null)) : remaining,
        expected_total: total,
        expected_prepaid_total: prepaid,
        expected_prepaid_token: bill.data?.prepaid_token,
        discard_drafts: discard,
        ...(printReceipt ? { print_receipt:true } : {}),
        ...(finalTotal !== total ? { final_total: finalTotal, offer_reason: currentOfferReason.trim() } : {}),
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

  const [displayUnavailable, setDisplayUnavailable] = useState(false);
  useEffect(() => {
    if (!id || !bill.data || bill.isError || bill.data.status !== 'PAYMENT_PENDING'
      || !validOffer || overpaid || pay.isPending || pay.isSuccess) return;
    let cancelled = false;
    const timer = window.setTimeout(() => {
      void api<{ status: string }>(`/table-sessions/${id}/customer-display`, 'POST', {
        expected_total: total, final_total: remaining, expected_prepaid_token: bill.data.prepaid_token,
      }).then((result) => {
        if (!cancelled) setDisplayUnavailable(result.status === 'unavailable');
      }).catch(() => { if (!cancelled) setDisplayUnavailable(true); });
    }, 300);
    return () => { cancelled = true; window.clearTimeout(timer); };
  }, [id, total, remaining, validOffer, overpaid, bill.data?.prepaid_token, bill.data?.status, bill.isError, pay.isPending, pay.isSuccess]);

  if (bill.isPending) return <><Loading /><ErrorBox error={bill.error} /></>;
  const blocked = bill.isError || pay.isPending || !bill.data?.item_count || bill.data?.status !== 'PAYMENT_PENDING'
    || (bill.data?.has_drafts && !discard) || !validOffer || overpaid
    || (!fullyPaid && method === 'CASH' && ((remaining > 0 && sen === null) || (sen !== null && sen < remaining)));

  return (
    <>
      <Link to={`/session/${id}`} className="back">← 查看订单</Link>
      <h1>{bill.data?.table} · 收款</h1>
      <ErrorBox error={bill.error || pay.error || resume.error} />
      {restoredOffer&&<p className="notice">此桌由误收款恢复，原收款已撤销。请重新核对金额及优惠后收款。</p>}
      {displayUnavailable && <p className="warning">顾客显示屏暂时无法连接，仍可正常收款。</p>}
      {bill.data?.prepaid_rounds?.map((round)=><p className="muted" key={round.batch_id}>订单 #{round.batch_id} · 已付款 {money(round.amount)} · {round.method?label(round.method):'方式未记录'}
        {round.amount_estimated && <span className="warning">（旧标记按该轮餐点估算，请返回订单核实并保存已付金额）</span>}</p>)}
      {bill.data?.status === 'OCCUPIED' && <p className="notice" role="status">
        此桌已恢复点餐，请返回订单页面重新核对账单并开始结账。
      </p>}
      <section className="card stack">
        <Lines items={bill.data?.items ?? []} />
        {bill.data?.table_notes && <p className="order-notes">整桌备注：{bill.data.table_notes}</p>}
        {bill.data?.order_notes?.map((note) => <p className="order-notes" key={note.batch_id}>订单 #{note.batch_id} 备注：{note.notes}</p>)}
        <div className="row spread"><span>餐点原价</span><strong>{money(total)}</strong></div>
        <label>优惠后总价 (RM)<input inputMode="decimal" value={finalText} disabled={pay.isPending}
          onChange={(event) => setOffer({ original: total, value: event.target.value })} /></label>
        <small>收银员可直接输入优惠后的最终总额，范围 RM 0.00 至 {money(total)}；餐点原价保留。</small>
        {!validOffer && <p className="error" role="alert">请输入不高于原价的有效金额，最多两位小数。</p>}
        {validOffer && finalTotal! < total && <>
          <div className="row spread"><span>优惠</span><strong>− {money(total-finalTotal!)}</strong></div>
          <label>优惠备注（选填）<input maxLength={240} value={currentOfferReason} disabled={pay.isPending}
            onChange={(event) => setOfferReason(event.target.value)} /></label>
        </>}
        {offer?.original === total && <button className="quiet" disabled={pay.isPending}
          onClick={() => { setOffer(null); setOfferReason(''); }}>恢复原价</button>}
        <div className="row spread"><h2>应收总额</h2><h1>{validOffer ? money(finalTotal!) : '请检查金额'}</h1></div>
        <div className="row spread"><strong>已付金额</strong><strong>{money(prepaid)}</strong></div>
        <div className="row spread"><strong>剩余应收</strong><strong>{validOffer ? money(remaining) : '请检查金额'}</strong></div>
        {overpaid && <p className="error" role="alert">已付超过应付，请先处理退款并更正已付金额。</p>}
        {fullyPaid && !overpaid && <p className="notice">已付全款，无需再次收款或选择付款方式。</p>}
        {!fullyPaid && <><div className="option-grid">
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
            <strong>{validOffer && sen !== null && sen >= remaining ? money(sen - remaining) : '金额不足或格式有误'}</strong>
          </div>
        </> : <p className="muted">请核实剩余款项到账后点击收款。系统会直接完成收款、清台并生成收据。</p>}</>}
        {bill.data?.has_drafts && (
          <label className="check warning">
            <input type="checkbox" checked={discard}
              onChange={(event) => setDiscard(event.target.checked)} />
            存在未下单草稿。我确认丢弃本桌全部草稿后收款。
          </label>
        )}
        <label className="check"><input type="checkbox" checked={printReceipt} disabled={pay.isPending}
          onChange={(event) => setPrintReceipt(event.target.checked)} />打印收据（默认不打印）</label>
        <button type="button" className="primary" disabled={!!blocked} onClick={() => pay.mutate()}>
          {pay.isPending ? '正在收款…' : fullyPaid ? '确认已付款并清台' : '确认收款并清台'}
        </button>
        <button onClick={() => resume.mutate()} disabled={resume.isPending || pay.isPending}>返回继续加单</button>
      </section>
    </>
  );
}
