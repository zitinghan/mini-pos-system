import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Link } from 'react-router-dom';
import { api } from '../services/api';
import type { Daily, Transaction } from '../services/types';
import { today, money, localTime } from '../utils/format';
import { label } from '../utils/i18n';
import { ErrorBox, Lines, Loading } from '../components/Common';

export const duration = (seconds: number | null | undefined) => seconds == null ? '暂无记录' : `${Math.round(seconds / 60)} 分钟`;

export default function History() {
  const [day, setDay] = useState(today());
  const summary = useQuery({ queryKey: ['sales', day], queryFn: () => api<Daily>(`/reports/daily-sales?day=${day}`), enabled: !!day, refetchInterval: 15000 });
  const history = useQuery({ queryKey: ['transactions', day], queryFn: () => api<Transaction[]>(`/reports/transactions?day=${day}`), enabled: !!day, refetchInterval: 15000 });
  const data = summary.data;
  const metrics = [
    ['今日营业额', money(data?.total ?? 0)], ['完成桌数', String(data?.completed_sessions ?? 0)],
    ['平均每桌', money(data?.average_spending ?? 0)], ['主食销售', money(data?.category_sales?.MAINS ?? 0)],
    ['小吃销售', money(data?.category_sales?.SNACKS ?? 0)], ['饮料销售', money(data?.category_sales?.DRINKS ?? 0)],
    ['啤酒销售', money(data?.category_sales?.BEER ?? 0)], ['平均用餐', duration(data?.dining_duration?.average_seconds)],
    ['最快一桌', duration(data?.dining_duration?.minimum_seconds)], ['最久一桌', duration(data?.dining_duration?.maximum_seconds)],
    ['现金', money(data?.methods.CASH ?? 0)], ['二维码', money(data?.methods.QR ?? 0)],
    ['其他收款', money(data?.methods.OTHER ?? 0)], ['啤酒数量', `${data?.beer_units ?? 0} 单位 / ${data?.beer_bottles ?? 0} 瓶`],
  ];
  return <>
    <div className="page-title"><div><p className="eyebrow">马来西亚时间 · MYR</p><h1>营业记录</h1></div></div>
    <label>营业日期<input aria-label="营业日期" type="date" value={day} onChange={(event) => setDay(event.target.value)} /></label>
    <ErrorBox error={summary.error || history.error} />
    {summary.isPending && <Loading />}
    <div className="summary-grid">{metrics.map(([name, value]) => <div className="card" key={name}><small>{name}</small><h2>{value}</h2></div>)}</div>
    <p className="muted">按收款完成日期统计。用餐从首次下单至成功收款，{data?.dining_duration?.count ?? 0} 桌具备有效时长。</p>
    <h2>已完成交易</h2>
    {history.data?.length === 0 && <p className="muted">当天暂无交易。</p>}
    {history.data?.map((transaction) => <details className="card" key={transaction.id}>
      <summary><strong>#{String(transaction.id).padStart(6, '0')} · {transaction.bill.table}</strong><span>{money(transaction.total)}</span><small>{localTime(transaction.created_at)} · {label(transaction.method)}</small></summary>
      <Lines items={transaction.bill.items} />
      {transaction.bill.order_notes?.map((note) => <p className="order-notes" key={note.batch_id}>订单 #{note.batch_id} 备注：{note.notes}</p>)}
      <p>实收 {money(transaction.received)} · 找零 {money(transaction.change)}</p>
      <small>用餐时长：{duration(transaction.bill.dining_duration_seconds)}</small>
      <Link className="back" to={`/receipts/${transaction.id}`}>查看 / 打印收据</Link>
    </details>)}
  </>;
}
