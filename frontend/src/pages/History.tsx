import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Link } from 'react-router-dom';
import { api } from '../services/api';
import type { Daily, Transaction } from '../services/types';
import { money, localTime } from '../utils/format';
import { label } from '../utils/i18n';
import { ErrorBox, Lines, Loading } from '../components/Common';

export const duration = (seconds: number | null | undefined) => seconds == null ? '暂无记录' : `${Math.round(seconds / 60)} 分钟`;

export default function History() {
  const [selectedDay, setSelectedDay] = useState<string | null>(null);
  const summary = useQuery({ queryKey: ['sales', selectedDay], queryFn: () => api<Daily>(`/reports/daily-sales${selectedDay ? `?day=${selectedDay}` : ''}`), enabled: selectedDay !== '', refetchInterval: 15000 });
  const day = selectedDay ?? summary.data?.date ?? '';
  const history = useQuery({ queryKey: ['transactions', day], queryFn: () => api<Transaction[]>(`/reports/transactions?day=${day}`), enabled: !!day, refetchInterval: 15000 });
  const data = summary.data;
  const metrics = [
    ['优惠前金额', money(data?.original_sales ?? data?.total ?? 0)], ['优惠合计', money(data?.discounts ?? 0)],
    ['本营业日营业额', money(data?.total ?? 0)], ['完成桌数', String(data?.completed_sessions ?? 0)],
    ['平均每桌', money(data?.average_spending ?? 0)], ['主食销售', money(data?.category_sales?.MAINS ?? 0)],
    ['小吃销售', money(data?.category_sales?.SNACKS ?? 0)], ['饮料销售', money(data?.category_sales?.DRINKS ?? 0)],
    ['啤酒销售', money(data?.category_sales?.BEER ?? 0)], ['平均用餐', duration(data?.dining_duration?.average_seconds)],
    ['最快一桌', duration(data?.dining_duration?.minimum_seconds)], ['最久一桌', duration(data?.dining_duration?.maximum_seconds)],
    ['现金', money(data?.methods.CASH ?? 0)], ['二维码', money(data?.methods.QR ?? 0)],
    ['其他收款', money(data?.methods.OTHER ?? 0)], ['啤酒数量', `${data?.beer_units ?? 0} 单位 / ${data?.beer_bottles ?? 0} 瓶`],
  ];
  return <>
    <div className="page-title"><div><p className="eyebrow">马来西亚时间 · MYR</p><h1>营业记录</h1></div></div>
    <label>营业日期<input aria-label="营业日期" type="date" value={day} onChange={(event) => setSelectedDay(event.target.value)} /></label>
    {selectedDay !== null && <button className="quiet" onClick={()=>setSelectedDay(null)}>当前营业日</button>}
    <ErrorBox error={summary.error || history.error} />
    {summary.isPending && <Loading />}
    <div className="summary-grid">{metrics.map(([name, value]) => <div className="card" key={name}><small>{name}</small><h2>{value}</h2></div>)}</div>
    <p className="muted">营业日按马来西亚时间中午 12:00 至次日中午 12:00 分界，凌晨收款计入前一天。按实际收款时间归属营业日。用餐从首次下单至成功收款，{data?.dining_duration?.count ?? 0} 桌具备有效时长。</p>
    <h2>已完成交易</h2>
    {history.data?.length === 0 && <p className="muted">当天暂无交易。</p>}
    {history.data?.map((transaction) => <details className="card" key={transaction.id}>
      <summary><strong>#{String(transaction.id).padStart(6, '0')} · {transaction.bill.table}{transaction.voided&&' · 收款已撤销'}</strong><span>{money(transaction.total)}</span><small>{localTime(transaction.created_at)} · {Object.keys(transaction.settlement?.allocations??{}).length>1?'混合付款':label(transaction.method)}</small></summary>
      <Lines items={transaction.bill.items} />
      {transaction.voided&&<p className="error">收款已撤销，不计入营业额。{transaction.reversal_reason}
        {transaction.restored_session_id&&<Link to={`/session/${transaction.restored_session_id}`}> 查看恢复后的桌台</Link>}</p>}
      {transaction.bill.table_notes && <p className="order-notes">整桌备注：{transaction.bill.table_notes}</p>}
      {transaction.bill.prepaid_rounds?.map((round)=><p key={round.batch_id}>订单 #{round.batch_id} · 已付 {money(round.amount)} · {round.method?label(round.method):'方式未记录'}</p>)}
      {!!transaction.settlement?.prepaid_total && <p>此前已付 {money(transaction.settlement.prepaid_total)} · 本次收款 {money(transaction.settlement.additional_collected)} · 剩余 RM 0.00</p>}
      {!!transaction.settlement?.prepaid_total && Object.entries(transaction.settlement.allocations).map(([method,amount])=><p key={method}>{label(method)}：{money(amount!)}</p>)}
      {transaction.bill.order_notes?.map((note) => <p className="order-notes" key={note.batch_id}>订单 #{note.batch_id} 备注：{note.notes}</p>)}
      {transaction.original_total != null && transaction.original_total !== transaction.total && <p>
        原价 {money(transaction.original_total)} · 优惠 {money(transaction.original_total-transaction.total)}
        {transaction.offer_reason && ` · ${transaction.offer_reason}`}</p>}
      <p>实收 {money(transaction.received)} · 找零 {money(transaction.change)}</p>
      <small>用餐时长：{duration(transaction.bill.dining_duration_seconds)}</small>
      <Link className="back" to={`/receipts/${transaction.id}`}>查看 / 打印收据</Link>
    </details>)}
  </>;
}
