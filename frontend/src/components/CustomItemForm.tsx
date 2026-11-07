import { useState } from 'react';
import type { CategoryCode, CustomItemInput, Line } from '../services/types';
import { money, parseSen } from '../utils/format';

export default function CustomItemForm({ category, initial, busy, onSave, onClose }: {
  category: CategoryCode; initial?: Line; busy: boolean; onSave: (value: CustomItemInput) => void; onClose?: () => void;
}) {
  const [name, setName] = useState(initial?.name ?? '');
  const [price, setPrice] = useState(initial ? (initial.unit_price / 100).toFixed(2) : '');
  const [quantity, setQuantity] = useState(initial?.quantity ?? 1);
  const [type, setType] = useState(initial?.category_code ?? category);
  const [stall, setStall] = useState<CustomItemInput['printer_group']>(initial?.printer_group ?? (['DRINKS', 'BEER'].includes(category) ? 'BEVERAGE' : 'KITCHEN'));
  const [takeaway, setTakeaway] = useState(initial?.takeaway ?? false);
  const [notes, setNotes] = useState(initial?.notes ?? '');
  const [bottles, setBottles] = useState(initial?.bottles_per_unit || 1);
  const unit = parseSen(price);
  const valid = !!name.trim() && !/[\x00-\x1f\x7f]/.test(name) && unit !== null && unit <= 1000000;
  const submitted = initial?.status === 'SUBMITTED';
  return <section className="card stack custom-item-form" aria-label="自定义餐点">
    <h2>{initial ? '修改自定义餐点' : '自定义餐点'}</h2>
    <label>餐点名称<input maxLength={120} value={name} disabled={busy} onChange={(event) => setName(event.target.value)} /></label>
    <label>单价 (RM)<input inputMode="decimal" value={price} placeholder="例如：8.50" disabled={busy} onChange={(event) => setPrice(event.target.value)} /></label>
    <small>单价支持 RM0 至 RM10,000，最多两位小数。</small>
    <label>分类<select value={type} disabled={busy || submitted} onChange={(event) => {
      const value = event.target.value as CategoryCode; setType(value); setStall(['DRINKS', 'BEER'].includes(value) ? 'BEVERAGE' : 'KITCHEN');
    }}><option value="MAINS">主食</option><option value="SNACKS">小吃</option><option value="DRINKS">饮料</option><option value="BEER">啤酒</option></select></label>
    <label>制作档口<select value={stall} disabled={busy || submitted} onChange={(event) => setStall(event.target.value as CustomItemInput['printer_group'])}>
      <option value="KITCHEN">面档</option><option value="RICE">饭档</option><option value="BEVERAGE">饮料档</option>
    </select></label>
    {submitted && <small>如需更换分类或档口，请先取消此项再重新加入。</small>}
    {type === 'BEER' && <label>每份瓶数<select value={bottles} disabled={busy} onChange={(event) => setBottles(Number(event.target.value))}>
      {Array.from({ length: 99 }, (_, index) => <option key={index+1} value={index+1}>{index+1}</option>)}
    </select></label>}
    <label className="check"><input type="checkbox" checked={takeaway} disabled={busy} onChange={(event) => setTakeaway(event.target.checked)} />打包</label>
    <label>餐点备注（选填）<input maxLength={240} value={notes} disabled={busy} onChange={(event) => setNotes(event.target.value)} /></label>
    <div className="row spread"><strong>{unit === null ? '请输入单价' : money(unit * quantity)}</strong><div className="quantity">
      <button type="button" aria-label="减少自定义数量" disabled={busy || quantity <= 1} onClick={() => setQuantity(quantity-1)}>−</button>
      <output>{quantity}</output><button type="button" aria-label="增加自定义数量" disabled={busy || quantity >= 99} onClick={() => setQuantity(quantity+1)}>+</button>
    </div></div>
    <button className="primary" disabled={busy || !valid} onClick={() => onSave({name:name.trim(),unit_price:unit!,quantity,
      category_code:type,printer_group:stall,takeaway,notes:notes.trim(),bottles_per_unit:type === 'BEER' ? bottles : 0})}>
      {busy ? '正在保存…' : `${initial ? '保存自定义修改' : '加入自定义草稿'}${unit !== null ? ` · ${money(unit * quantity)}` : ''}`}</button>
    {onClose && <button disabled={busy} onClick={onClose}>收起自定义餐点</button>}
  </section>;
}
