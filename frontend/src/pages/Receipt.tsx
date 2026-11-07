import { useEffect, useState } from 'react';
import type { CSSProperties } from 'react';
import { Link, useParams } from 'react-router-dom';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { api, previewJob, requestKey, clearKey } from '../services/api';
import type { CustomerReceipt } from '../services/types';
import { ErrorBox, Loading, ConfirmButton } from '../components/Common';
import { localTime, money } from '../utils/format';
import { label } from '../utils/i18n';

export function ReceiptPaper({ receipt }: { receipt: CustomerReceipt }) {
  return <article className="receipt-paper" aria-label="客户收据">
    <div className="receipt-brand">{receipt.restaurant}</div>
    <p className="receipt-english">{receipt.english_name}</p>
    <h2>收据 / RECEIPT</h2>
    <div className="receipt-meta"><strong>{receipt.receipt_number}</strong><strong>桌号 {receipt.table}</strong></div>
    <small>{localTime(receipt.time)}</small><small>收银：{receipt.cashier}</small>
    <div className="receipt-items">{receipt.items.map((item) => <div className="receipt-line" key={item.id}>
      <div className="row spread"><strong>{item.quantity} × {item.name}</strong><strong>{money(item.line_total)}</strong></div>
      {item.modifiers.length > 0 && <p>{item.modifiers.map((modifier) => modifier.name).join(' · ')}</p>}
      {item.description && <p>{item.description}</p>}
      {!!item.physical_bottles && <p>共 {item.physical_bottles} 瓶</p>}
      {item.notes && <p>备注：{item.notes}</p>}
      <small>{item.quantity} × {money(item.unit_price)}</small>
    </div>)}</div>
    <div className="receipt-total"><strong>合计 TOTAL</strong><strong>{money(receipt.total)}</strong></div>
    <div className="receipt-meta"><span>付款方式</span><strong>{label(receipt.method)}</strong></div>
    <div className="receipt-meta"><span>实收</span><strong>{money(receipt.received)}</strong></div>
    <div className="receipt-meta"><span>找零</span><strong>{money(receipt.change)}</strong></div>
    <p className="receipt-thanks">谢谢光临 · THANK YOU</p>
  </article>;
}

export default function Receipt() {
  const { paymentId } = useParams();
  const client = useQueryClient();
  const [image, setImage] = useState<string | null>(null);
  const [error, setError] = useState<unknown>(null);
  const receipt = useQuery({ queryKey: ['receipt', paymentId], queryFn: () => api<CustomerReceipt>(`/payments/${paymentId}/receipt`), refetchInterval: 4000 });
  const job = receipt.data?.print_job;
  const refresh = () => { void client.invalidateQueries({ queryKey: ['receipt', paymentId] }); };
  const send = useMutation({ mutationFn: async () => {
    const scope = `receipt-first-print:${paymentId}`;
    const result = await api(`/payments/${paymentId}/receipt/print`, 'POST', undefined, requestKey(scope));
    clearKey(scope); return result;
  }, onSuccess: refresh });
  const retry = useMutation({ mutationFn: async () => {
    const scope = `receipt-reprint:${job?.id}`;
    const result = await api(`/print-jobs/${job?.id}/retry`, 'POST', undefined, requestKey(scope));
    clearKey(scope); return result;
  }, onSuccess: refresh });
  useEffect(() => () => { if (image) URL.revokeObjectURL(image); }, [image]);
  if (receipt.isPending) return <><Loading /><ErrorBox error={receipt.error} /></>;
  if (!receipt.data) return <ErrorBox error={receipt.error} />;
  const data = receipt.data;
  const waiting = !!job && ['PENDING', 'SENDING'].includes(job.status);
  const paperWidth = `${data.paper_mm ?? (data.paper_width >= 500 ? 80 : 58)}mm`;
  return <section className="customer-receipt" style={{ '--receipt-width': paperWidth } as CSSProperties}>
    <style>{`@media print { @page { size: ${paperWidth} auto; margin: 3mm; } }`}</style>
    <div className="no-print"><h1>付款收据</h1><p className="notice">收款已完成，桌台已释放。{job ? '收银收据已建立打印任务。' : '可查看或打印这笔历史交易的收据。'}</p>
      <div className="receipt-actions"><Link className="back" to="/">← 返回桌台</Link><button onClick={() => window.print()}>浏览器打印 / 保存 PDF</button></div>
      <div className="card stack"><h2>收银打印状态</h2>
        {job ? <><span className={`print-status ${job.status}`}>{label(job.status)}</span>
          {(job.printer_mode ?? data.configured_printer_mode) === 'mock' && <p className="warning">当前为预览模式，未发送到实体收银打印机。</p>}
          {job.status === 'SENT' && job.printer_mode !== 'mock' && <small>已提交至打印机 / Windows 队列，请检查实际出纸。</small>}
          {job.error && <p className="error">{job.error}</p>}
          {job.preview && <button onClick={() => { previewJob(job.id).then(setImage).catch(setError); }}>查看收据打印预览</button>}
          {!waiting && <ConfirmButton disabled={retry.isPending} onConfirm={() => retry.mutate()}>核实后重印收据</ConfirmButton>}
        </> : <button disabled={send.isPending} onClick={() => send.mutate()}>发送到收银打印机</button>}
        <ErrorBox error={receipt.error || send.error || retry.error || error} />
      </div>
    </div>
    <ReceiptPaper receipt={data} />
    {image && <div className="modal no-print" role="dialog" aria-modal="true" aria-label="收据打印预览"
      onClick={(event) => { if (event.target === event.currentTarget) setImage(null); }}><div className="stack"><button onClick={() => setImage(null)}>关闭预览</button><img className="ticket-preview" src={image} alt="客户收据及付款金额" /></div></div>}
  </section>;
}
