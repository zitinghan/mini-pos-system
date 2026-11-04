import {useState} from 'react';
import {useQuery} from '@tanstack/react-query';
import {api} from '../services/api';
import type {Daily,Transaction} from '../services/types';
import {today,money,localTime} from '../utils/format';
import {label} from '../utils/i18n';
import {ErrorBox,Lines,Loading} from '../components/Common';
export default function History(){const[day,setDay]=useState(today());
 const summary=useQuery({queryKey:['sales',day],queryFn:()=>api<Daily>(`/reports/daily-sales?day=${day}`),enabled:!!day,refetchInterval:15000});
 const history=useQuery({queryKey:['transactions',day],queryFn:()=>api<Transaction[]>(`/reports/transactions?day=${day}`),enabled:!!day,refetchInterval:15000});
 return <><div className="page-title"><div><p className="eyebrow">马来西亚时间 · MYR</p><h1>营业记录</h1></div></div><label>营业日期<input aria-label="营业日期" type="date" value={day} onChange={e=>setDay(e.target.value)}/></label><ErrorBox error={summary.error||history.error}/>{summary.isPending&&<Loading/>}<div className="summary-grid"><div className="card"><small>今日营业额</small><h2>{money(summary.data?.total??0)}</h2><p>{summary.data?.transactions??0} 笔交易</p></div>{Object.entries(summary.data?.methods??{}).map(([method,total])=><div className="card" key={method}><small>{label(method)}</small><h2>{money(total)}</h2></div>)}</div><h2>已完成交易</h2>{history.data?.length===0&&<p className="muted">当天暂无交易。</p>}{history.data?.map(transaction=><details className="card" key={transaction.id}><summary><strong>#{String(transaction.id).padStart(6,'0')} · {transaction.bill.table}</strong><span>{money(transaction.total)}</span><small>{localTime(transaction.created_at)} · {label(transaction.method)}</small></summary><Lines items={transaction.bill.items}/><p>实收 {money(transaction.received)} · 找零 {money(transaction.change)}</p></details>)}</>;
}
