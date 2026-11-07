import {useState} from 'react';
import type {Line} from '../services/types';
import {money} from '../utils/format';
import {label} from '../utils/i18n';
import {visibleModifiers} from '../utils/modifiers';
export function ErrorBox({error}:{error:unknown}){return error?<div role="alert" className="error">{error instanceof Error?error.message:String(error)}</div>:null;}
export function Loading(){return <p role="status" className="muted">正在加载…</p>;}
export function Lines({ items, onEdit, onCancel, onRemove }: { items: Line[]; onEdit?: (item: Line) => void; onCancel?: (item: Line) => void; onRemove?: (item: Line) => void }) {
  return <div>{items.map((item) => <div className={`line ${item.status === 'CANCELLED' ? 'cancelled' : ''}`} key={item.id}>
    <div><strong>{item.quantity} × {item.name}</strong>{item.description && <small>{item.description}</small>}
      {visibleModifiers(item.modifiers).length > 0 && <small>{visibleModifiers(item.modifiers).map((modifier) => modifier.name).join(' · ')}</small>}
      {!!item.physical_bottles && <small>共 {item.physical_bottles} 瓶</small>}
      {item.notes && <small>备注：{item.notes}</small>}
      {item.cancellation_reason && <small>取消原因：{item.cancellation_reason}</small>}
      <small>{money(item.unit_price)} / 份 · {label(item.status)}</small>
      {item.status !== 'CANCELLED' && (onEdit || onCancel || onRemove) && <div className="row">
        {onEdit && <button className="quiet" aria-label={`修改 ${item.quantity} × ${item.name}`} onClick={() => onEdit(item)}>修改</button>}
        {onRemove && <button className="quiet" aria-label={`移除 ${item.quantity} × ${item.name}`} onClick={() => onRemove(item)}>移除</button>}
        {onCancel && <button className="quiet" aria-label={`取消 ${item.quantity} × ${item.name}`} onClick={() => onCancel(item)}>取消此项</button>}
      </div>}
    </div><strong>{money(item.line_total)}</strong>
  </div>)}</div>;
}
export function ConfirmButton({onConfirm,children,disabled=false}:{onConfirm:()=>void;children:React.ReactNode;disabled?:boolean}){const[confirm,setConfirm]=useState(false);return confirm?<div className="confirm"><p>确认执行此操作？</p><div className="row"><button type="button" onClick={()=>setConfirm(false)}>返回</button><button type="button" className="primary" disabled={disabled} onClick={()=>{onConfirm();setConfirm(false);}}>确认</button></div></div>:<button type="button" disabled={disabled} onClick={()=>setConfirm(true)}>{children}</button>;}
