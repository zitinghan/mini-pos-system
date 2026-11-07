import { useEffect, useRef, useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { api, requestKey, clearKey } from '../services/api';
import type { MenuItem, Batch, Bill, CategoryCode, Line } from '../services/types';
import { useAuth } from '../stores/auth';
import { useUI } from '../stores/ui';
import { money } from '../utils/format';
import { label } from '../utils/i18n';
import { Lines, ErrorBox, Loading, ConfirmButton } from '../components/Common';

interface PickerProps {
  item: MenuItem;
  onAdd: (quantity: number, ids: number[], notes?: string, unitPrice?: number) => void;
  busy: boolean;
  initial?: Line;
}

function startingPrice(item: MenuItem) {
  const variants = item.groups.flatMap((group) => group.options.filter((option) => option.enabled !== false && option.unit_price != null).map((option) => option.unit_price!));
  return variants.length ? Math.min(...variants) : item.base_price;
}

export function MenuItemButton({ item, selected, onSelect }: { item: MenuItem; selected: boolean; onSelect: (item: MenuItem) => void }) {
  return <button className={`food-button ${item.sold_out ? 'sold-out' : ''} ${selected ? 'selected' : ''}`}
    disabled={item.sold_out} onClick={() => onSelect(item)}>
    <span>{item.name}</span><small>{money(startingPrice(item))} 起</small>
    {item.sold_out ? <span className="sold-out-label">SOLD OUT · 已售罄</span>
      : item.promotion && <span className="promotion-label">限时优惠 · 热 / 冷同价</span>}
    {item.description && <small>{item.description}</small>}
  </button>;
}

export function ItemPicker({ item, onAdd, busy, initial }: PickerProps) {
  const [selected, setSelected] = useState<number[]>(
    initial ? [...initial.modifiers.map((entry) => entry.option_id), ...item.groups.filter((group) => ['用餐方式', '份量'].includes(group.name)
      && !group.options.some((option) => initial.modifiers.some((entry) => entry.option_id === option.id)))
      .flatMap((group) => group.options.filter((option) => option.is_default && option.enabled !== false).map((option) => option.id))]
      : item.groups.flatMap((group) => group.options.filter((option) => option.is_default && option.enabled !== false).map((option) => option.id)),
  );
  const [quantity, setQuantity] = useState(initial?.quantity ?? 1);
  const [notes, setNotes] = useState(initial?.notes ?? '');
  const allOptions = item.groups.flatMap((group) => group.options);
  const selectedOptions = allOptions.filter((option) => selected.includes(option.id));
  const iceIds = new Set(item.groups.filter((group) => group.name === '冰量').flatMap((group) => group.options.map((option) => option.id)));
  const visibleGroups = item.groups.filter((group) => group.name !== '冰量' || group.options.some((option) =>
    option.enabled !== false && !selectedOptions.some((entry) => entry.incompatible_with?.includes(option.id) || option.incompatible_with?.includes(entry.id))));
  const displayGroups = [...visibleGroups.filter((group) => group.name === '用餐方式'),
    ...visibleGroups.filter((group) => group.name !== '用餐方式')];
  const variant = selectedOptions.find((option) => option.unit_price != null);
  const pricedIds = new Set(item.groups.filter((group) => group.options.some((option) => option.unit_price != null
    || option.price > 0 || initial?.modifiers.some((entry) => entry.option_id === option.id && entry.price > 0)))
    .flatMap((group) => group.options.filter((option) => !(option.is_default && option.price === 0 && option.unit_price == null
      && !initial?.modifiers.some((entry) => entry.option_id === option.id && entry.price > 0))).map((option) => option.id)));
  const oldPriced = new Set(initial?.modifiers.filter((entry) => pricedIds.has(entry.option_id)).map((entry) => entry.option_id));
  const newPriced = selected.filter((identity) => pricedIds.has(identity));
  const keepPrice = initial?.status === 'SUBMITTED' && oldPriced.size === newPriced.length && newPriced.every((identity) => oldPriced.has(identity));
  const price = keepPrice ? initial.unit_price : (variant?.unit_price ?? item.base_price) + selectedOptions.reduce((sum, option) => sum + option.price, 0);
  const valid = item.groups.every((group) => {
    const count = group.options.filter((option) => selected.includes(option.id)).length;
    return count >= group.minimum && count <= group.maximum;
  }) && !selectedOptions.some((option) => option.incompatible_with?.some((id) => selected.includes(id)));

  return (
    <section className="card stack">
      <h2>{item.name}</h2>
      {item.sold_out && <p className="warning" role="status">SOLD OUT · 已售罄，请选择其他项目。</p>}
      {item.promotion && <p className="promotion">限时 {money(item.promotion.unit_price)} · 至 {item.promotion.ends_on}（马来西亚时间）</p>}
      {item.description && <p className="muted">{item.description}</p>}
      {displayGroups.map((group) => (
        <fieldset key={group.id}>
          <legend>{group.name} <small>{group.name === '用餐方式' ? '默认堂食' : group.minimum > 0 ? '必选' : '可选'}</small></legend>
          <div className="option-grid">
            {group.options.filter((option) => option.enabled !== false).map((option) => (
              <button type="button" key={option.id}
                disabled={!selected.includes(option.id) && selectedOptions.some((entry) =>
                  !(group.name === '温度' && iceIds.has(entry.id)) &&
                  (entry.incompatible_with?.includes(option.id) || option.incompatible_with?.includes(entry.id)))}
                aria-pressed={selected.includes(option.id)}
                className={selected.includes(option.id) ? 'selected' : ''}
                onClick={() => setSelected((previous) => {
                  const compatible = group.name === '温度' ? previous.filter((id) => !iceIds.has(id) || !allOptions.some((entry) =>
                    entry.id === id && (entry.incompatible_with?.includes(option.id) || option.incompatible_with?.includes(id)))) : previous;
                  if (group.maximum === 1) {
                    if (group.minimum === 0 && group.name !== '用餐方式' && compatible.includes(option.id)) {
                      return compatible.filter((id) => id !== option.id);
                    }
                    return [...compatible.filter((id) => !group.options.some((entry) => entry.id === id)), option.id];
                  }
                  return compatible.includes(option.id)
                    ? compatible.filter((id) => id !== option.id) : [...compatible, option.id];
                })}>
                {option.name}
                {option.unit_price != null ? <small>{money(option.unit_price)}</small>
                  : option.price > 0 && <small>+ {money(option.price)}</small>}
              </button>
            ))}
          </div>
        </fieldset>
      ))}
      <div className="row spread">
        <strong>{money(price)} / 份</strong>
        <div className="quantity">
          <button type="button" aria-label="减少数量" disabled={quantity === 1}
            onClick={() => setQuantity((value) => value - 1)}>−</button>
          <output>{quantity}</output>
          <button type="button" aria-label="增加数量" disabled={quantity === 99}
            onClick={() => setQuantity((value) => value + 1)}>+</button>
        </div>
      </div>
      {!!variant?.bottles && <p>{quantity} × {variant.name} · 共 {quantity * variant.bottles} 瓶</p>}
      <label>备注（可选）<input maxLength={240} value={notes} onChange={(event) => setNotes(event.target.value)} /></label>
      <button type="button" className="primary" disabled={busy || !valid || item.sold_out}
        onClick={() => initial ? onAdd(quantity, selected, notes.trim(), price) : notes.trim() ? onAdd(quantity, selected, notes.trim()) : onAdd(quantity, selected)}>
        {item.sold_out ? 'SOLD OUT · 已售罄' : busy ? '正在保存…' : `${initial ? '保存修改' : '加入草稿'} · ${money(price * quantity)}`}
      </button>
    </section>
  );
}

export default function Session() {
  const { id } = useParams();
  const client = useQueryClient();
  const navigate = useNavigate();
  const user = useAuth((state) => state.user);
  const [chosen, setChosen] = useState<MenuItem | null>(null);
  const optionsRef = useRef<HTMLDivElement>(null);
  const [category, setCategory] = useState<CategoryCode>('MAINS');
  const [error, setError] = useState<unknown>(null);
  const [editing, setEditing] = useState<{ line: Line; batchId: number } | null>(null);
  const [orderNotes, setOrderNotes] = useState<string | null>(null);
  const [draftPaid, setDraftPaid] = useState<boolean | null>(null);
  const [tableNotes, setTableNotes] = useState<string | null>(null);
  const [roundDetails, setRoundDetails] = useState<Batch | null>(null);
  const [roundNotes, setRoundNotes] = useState('');
  const [roundPaid, setRoundPaid] = useState(false);
  const [cancelTarget, setCancelTarget] = useState<{kind:'ITEM';line:Line;batchId:number} | {kind:'TABLE';bill:Bill} | null>(null);
  const [cancelReason, setCancelReason] = useState('顾客取消');
  const bill = useQuery({
    queryKey: ['bill', id],
    queryFn: () => api<Bill>(`/table-sessions/${id}/bill`),
    refetchInterval: 4000,
  });
  const batches = useQuery({
    queryKey: ['batches', id],
    queryFn: () => api<Batch[]>(`/table-sessions/${id}/orders`),
    refetchInterval: 4000,
  });
  const menu = useQuery({
    queryKey: ['menu'],
    queryFn: () => api<MenuItem[]>('/menu'),
    refetchInterval: 4000,
  });
  const refresh = () => {
    void client.invalidateQueries({ queryKey: ['batches', id] });
    void client.invalidateQueries({ queryKey: ['bill', id] });
  };
  const ownDraft = batches.data?.find((batch) => batch.status === 'DRAFT' && batch.user_id === user?.id);
  const drafts = ownDraft?.items.filter((item) => item.status === 'DRAFT') ?? [];
  const unavailableDrafts = drafts.filter((item) => menu.data?.some((entry) => entry.id === item.menu_item_id && entry.sold_out));
  const currentChosen = chosen ? menu.data?.find((item) => item.id === chosen.id) ?? chosen : null;
  const editingMenu = editing ? menu.data?.find((item) => item.id === editing.line.menu_item_id) : null;
  useEffect(() => { setOrderNotes(null); setDraftPaid(null); }, [ownDraft?.id]);

  const saveTableNotes = useMutation({
    mutationFn: async () => {
      const payload = { notes: tableNotes ?? bill.data?.table_notes ?? '', expected_revision: bill.data?.metadata_revision };
      const scope = `table-notes:${id}:${JSON.stringify(payload)}`;
      const result = await api(`/table-sessions/${id}/notes`, 'PATCH', payload, requestKey(scope));
      clearKey(scope); return result;
    },
    onSuccess: async () => { setTableNotes(null); await client.invalidateQueries({ queryKey: ['bill', id] }); void client.invalidateQueries({ queryKey: ['print-jobs'] }); },
  });
  const saveRoundDetails = useMutation({
    mutationFn: async () => {
      if (!roundDetails) throw new Error('请选择订单');
      const payload = { notes: roundNotes, prepaid_label: roundPaid, expected_revision: roundDetails.info_revision ?? 1 };
      const scope = `batch-details:${roundDetails.id}:${JSON.stringify(payload)}`;
      const result = await api(`/order-batches/${roundDetails.id}/details`, 'PATCH', payload, requestKey(scope));
      clearKey(scope); return result;
    },
    onSuccess: () => { setRoundDetails(null); refresh(); void client.invalidateQueries({ queryKey: ['print-jobs'] }); useUI.getState().setNotice('备注 / 付款标记已更新，已通知相关档口。'); },
  });
  const cancelOrder = useMutation({
    mutationFn: async () => {
      if (!cancelTarget) throw new Error('请选择要取消的内容');
      const payload = cancelTarget.kind === 'ITEM'
        ? { expected_revision: cancelTarget.line.revision ?? 1, reason: cancelReason.trim() }
        : { expected_change_token: cancelTarget.bill.change_token, reason: cancelReason.trim() };
      const path = cancelTarget.kind === 'ITEM'
        ? `/order-batches/${cancelTarget.batchId}/items/${cancelTarget.line.id}/cancel` : `/table-sessions/${id}/cancel`;
      const scope = `cancel:${path}:${JSON.stringify(payload)}`;
      const result = await api<{status:string;print_jobs:{id:number}[]}>(path, 'POST', payload, requestKey(scope));
      clearKey(scope); return { ...result, wholeTable: cancelTarget.kind === 'TABLE' };
    },
    onSuccess: (result) => {
      setCancelTarget(null); refresh();
      void client.invalidateQueries({ queryKey: ['tables'] }); void client.invalidateQueries({ queryKey: ['print-jobs'] });
      useUI.getState().setNotice(result.wholeTable ? '整桌已取消并释放，请通知档口停止制作。' : '餐点已取消，账单已更新，取消单已送至对应档口。');
      if (result.wholeTable) navigate('/');
    },
  });
  const startCancelItem = (line: Line, batchId: number) => { cancelOrder.reset(); setCancelReason('顾客取消'); setCancelTarget({kind:'ITEM',line,batchId}); };

  const edit = useMutation({
    mutationFn: async ({ quantity, ids, notes = '', unitPrice }: { quantity: number; ids: number[]; notes?: string; unitPrice?: number }) => {
      if (!editing) throw new Error('请选择要修改的餐点');
      const payload = { menu_item_id: editing.line.menu_item_id, quantity, option_ids: [...ids].sort((a, b) => a - b),
        notes, expected_revision: editing.line.revision ?? 1, expected_unit_price: unitPrice };
      const scope = `edit:${editing.batchId}:${editing.line.id}:${JSON.stringify(payload)}`;
      const result = await api<Line & {change_print_job_id?:number}>(`/order-batches/${editing.batchId}/items/${editing.line.id}`, 'PATCH', payload, requestKey(scope));
      clearKey(scope);
      return result;
    },
    onSuccess: (result) => {
      setEditing(null); refresh();
      void client.invalidateQueries({ queryKey: ['print-jobs'] });
      useUI.getState().setNotice(result.change_print_job_id ? '餐点已修改，更改单已送入对应档口打印队列。' : '草稿修改已保存。');
    },
  });
  const startEdit = (line: Line, batchId: number) => { edit.reset(); setEditing({ line, batchId }); };

  const add = useMutation({
    mutationFn: async ({ quantity, ids, notes = '' }: { quantity: number; ids: number[]; notes?: string }) => {
      if (!chosen) throw new Error('请选择菜品');
      if (currentChosen?.sold_out) throw new Error(`${currentChosen.name} 已售罄，请选择其他项目。`);
      const batch = ownDraft ?? await api<{ id: number }>('/order-batches', 'POST', {
        session_id: Number(id),
      });
      const payload = { menu_item_id: chosen.id, quantity, option_ids: [...ids].sort((a, b) => a - b), notes };
      // Retain the same request identity if the response is lost, including across reloads.
      const scope = `add:${batch.id}:${JSON.stringify(payload)}`;
      await api(`/order-batches/${batch.id}/items`, 'POST', payload, requestKey(scope));
      clearKey(scope);
      return chosen.id;
    },
    onSuccess: (addedItemId) => {
      setChosen((current) => current?.id === addedItemId ? null : current);
      setError(null);
      refresh();
    },
    onError: setError,
  });
  const submit = useMutation({
    mutationFn: async () => {
      if (!ownDraft) throw new Error('草稿不存在');
      if (tableNotes !== null && tableNotes !== (bill.data?.table_notes ?? '')) await saveTableNotes.mutateAsync();
      const payload = { notes: orderNotes ?? ownDraft.notes ?? '', prepaid_label: draftPaid ?? ownDraft.prepaid_label ?? false };
      const scope = `submit:${ownDraft.id}:${JSON.stringify(payload)}`;
      const result = await api<{ batch_id: number; status?:string; print_job_id: number; print_jobs?: {id:number;routing_group:string}[] }>(
        `/order-batches/${ownDraft.id}/submit`, 'POST', payload, requestKey(scope),
      );
      clearKey(scope);
      return result;
    },
    onSuccess: (result) => {
      refresh();
      useUI.getState().setNotice(
        result.status === 'CANCELLED' ? `订单 #${result.batch_id} 已取消，不会重新下单。` : `订单 #${result.batch_id} 已保存；${result.print_jobs?.length ?? 1} 张制作单已排队，请在订单页查看面档 / 饭档 / 饮料档发送状态。`,
      );
      navigate('/');
    },
    onError: setError,
  });
  const discard = useMutation({
    mutationFn: () => api(`/order-batches/${ownDraft?.id}`, 'DELETE'),
    onSuccess: refresh,
    onError: setError,
  });
  const remove = useMutation({
    mutationFn: (itemId: number) => api(`/order-batches/${ownDraft?.id}/items/${itemId}`, 'DELETE'),
    onSuccess: refresh,
    onError: setError,
  });
  const resume = useMutation({
    mutationFn: () => api(`/table-sessions/${id}/resume`, 'POST'),
    onSuccess: refresh,
    onError: setError,
  });
  const closeEmpty = useMutation({
    mutationFn: () => api(`/table-sessions/${id}/close-empty`, 'POST'),
    onSuccess: () => navigate('/'),
    onError: setError,
  });
  const checkout = useMutation({
    mutationFn: () => api(`/table-sessions/${id}/checkout`, 'POST'),
    onSuccess: () => navigate(`/checkout/${id}`),
    onError: setError,
  });

  useEffect(() => {
    if (bill.data?.status === 'PAID') setChosen(null);
  }, [bill.data?.status]);

  useEffect(() => {
    if (chosen) optionsRef.current?.scrollIntoView?.({ behavior: 'smooth', block: 'start' });
  }, [chosen]);

  if (bill.isPending || batches.isPending || menu.isPending) {
    return <><Loading /><ErrorBox error={bill.error || batches.error || menu.error} /></>;
  }
  const active = bill.data?.status === 'OCCUPIED';
  const cashier = user?.role === 'ADMIN' && ['OCCUPIED', 'PAYMENT_PENDING'].includes(bill.data?.status ?? '');

  return (
    <>
      <Link className="back" to="/">← 返回桌台</Link>
      <div className="page-title">
        <div><p className="eyebrow">{bill.data?.first_order_at || bill.data?.item_count ? label(bill.data?.status ?? '') : '尚未下单'}</p><h1>{bill.data?.table} 点餐</h1></div>
        <strong>{money(bill.data?.total ?? 0)}</strong>
      </div>
      <ErrorBox error={error || bill.error || batches.error || menu.error || (!editing && edit.error)} />
      {bill.data?.status === 'PAYMENT_PENDING' && (
        <div className="notice" role="status">
          <p>此桌正在结账。需要加单时，请收银员恢复点餐。</p>
          {cashier && <button disabled={resume.isPending} onClick={() => resume.mutate()}>
            继续加单
          </button>}
        </div>
      )}
      {active && <>
        <div className="category-tabs" role="group" aria-label="菜品分类">
          {([['MAINS', '主食', 'Mains'], ['SNACKS', '小吃', 'Snacks'], ['DRINKS', '饮料', 'Drinks'], ['BEER', '啤酒', 'Beer']] as const).map(([code, name, english]) => (
            <button key={code} aria-pressed={category === code} onClick={() => { setCategory(code); setChosen(null); }}>
              {name}<small>{english}</small>
            </button>
          ))}
        </div>
        <div className="food-grid">
          {menu.data?.filter((item) => (item.category_code ?? 'MAINS') === category).map((item) => (
            <MenuItemButton key={item.id} item={item} selected={chosen?.id === item.id}
              onSelect={(selected) => setChosen({ ...selected })} />
          ))}
        </div>
        {currentChosen && <div ref={optionsRef} style={{ scrollMarginTop: 16 }}>
          <ItemPicker key={currentChosen.id} item={currentChosen} busy={add.isPending}
            onAdd={(quantity, ids, notes) => add.mutate({ quantity, ids, notes })} />
        </div>}
      </>}
      {ownDraft && (
        <section className="card stack">
          <div className="row spread"><h2>当前草稿</h2><span className="pill">未送厨房</span></div>
          <Lines items={drafts} onEdit={active && !edit.isPending ? (line) => startEdit(line, ownDraft.id) : undefined} />
          {drafts.map((item) => (
            <button key={item.id} className="quiet" disabled={remove.isPending}
              onClick={() => remove.mutate(item.id)}>移除 {item.quantity} × {item.name}</button>
          ))}
          <strong>预计 {money(drafts.reduce((sum, item) => sum + item.line_total, 0))}</strong>
          <label>整单备注（选填）<textarea maxLength={500} rows={2} value={orderNotes ?? ownDraft.notes ?? ''}
            onChange={(event) => setOrderNotes(event.target.value)} placeholder="例如：一起上菜、先出饮料" /></label>
          <label className="check"><input type="checkbox" checked={draftPaid ?? ownDraft.prepaid_label ?? false}
            onChange={(event) => setDraftPaid(event.target.checked)} />本轮已付款（仅手动标记）</label>
          <small>只作订单提示，不登记收款或自动清台；下一轮默认不标记。</small>
          <small>价格以确认下单时菜单为准。</small>
          {unavailableDrafts.length > 0 && <p className="warning" role="alert">{unavailableDrafts.map((item) => item.name).join('、')} 已售罄，请先移除或等待恢复供应。</p>}
          <button className="primary" disabled={!active || !drafts.length || unavailableDrafts.length > 0 || submit.isPending || add.isPending || edit.isPending || cancelOrder.isPending || saveTableNotes.isPending}
            onClick={() => submit.mutate()}>
            {submit.isPending ? '正在确认…' : '确认下单 / 送档口'}
          </button>
          <ConfirmButton disabled={discard.isPending} onConfirm={() => discard.mutate()}>丢弃此草稿</ConfirmButton>
        </section>
      )}
      <section className="card stack">
        <h2>已下单 · 桌台账单</h2>
        {batches.data?.filter((batch) => batch.status !== 'DRAFT').map((batch) => (
          <div key={batch.id}>
            <p className="batch-heading">#{batch.id} · {label(batch.status)}</p>
            {batch.prepaid_label && <strong className="pill">已付款（手动标记）</strong>}
            {batch.notes && <p className="order-notes">整单备注：{batch.notes}</p>}
            {active && batch.status === 'SUBMITTED' && <button className="quiet" onClick={() => {
              saveRoundDetails.reset(); setRoundDetails(batch); setRoundNotes(batch.notes ?? ''); setRoundPaid(batch.prepaid_label ?? false);
            }}>修改本轮备注 / 付款标记</button>}
            <Lines items={batch.items} onEdit={active && batch.status === 'SUBMITTED' && !edit.isPending && !cancelOrder.isPending ? (line) => startEdit(line, batch.id) : undefined}
              onCancel={active && batch.status === 'SUBMITTED' && !edit.isPending && !cancelOrder.isPending ? (line) => startCancelItem(line, batch.id) : undefined} />
          </div>
        ))}
        {!bill.data?.items.length && <p className="muted">尚未确认任何菜品。</p>}
        <div className="row spread"><h2>合计</h2><h2>{money(bill.data?.total ?? 0)}</h2></div>
        {cashier && <button className="primary" disabled={checkout.isPending || edit.isPending || cancelOrder.isPending || saveRoundDetails.isPending || saveTableNotes.isPending || !bill.data?.item_count}
          onClick={() => checkout.mutate()}>查看账单 / 收款</button>}
        {active && bill.data?.change_token && <button className="quiet" disabled={cancelOrder.isPending || edit.isPending || add.isPending || submit.isPending}
          onClick={() => { cancelOrder.reset(); setCancelReason('顾客取消'); setCancelTarget({kind:'TABLE',bill:bill.data}); }}>取消整桌</button>}
        {cashier && !bill.data?.item_count && !bill.data?.change_token && (
          <ConfirmButton disabled={closeEmpty.isPending} onConfirm={() => closeEmpty.mutate()}>
            取消草稿并释放空桌
          </ConfirmButton>
        )}
      </section>
      {batches.data?.filter((batch) => batch.status === 'DRAFT' && batch.user_id !== user?.id).map((batch) => (
        <section className="card" key={batch.id}>
          <h2>其他员工草稿 #{batch.id}</h2>
          <Lines items={batch.items.filter((item) => item.status === 'DRAFT')} />
        </section>
      ))}
      {bill.data?.metadata_revision != null && <section className="card stack table-notes">
        <label>整桌备注（所有轮次）<textarea rows={2} maxLength={500} disabled={!active} value={tableNotes ?? bill.data.table_notes ?? ''}
          onChange={(event) => setTableNotes(event.target.value)} placeholder="例如：赶时间、先上饮料" /></label>
        <ErrorBox error={saveTableNotes.error} />
        <button disabled={!active || saveTableNotes.isPending || tableNotes === null || tableNotes === (bill.data.table_notes ?? '')}
          onClick={() => saveTableNotes.mutate()}>保存整桌备注</button>
        <small>下单后也可修改。只发送备注更新通知，不会重复制作餐点。</small>
      </section>}
      {editing && <div className="modal" role="dialog" aria-modal="true" aria-label="修改餐点"
        onClick={(event) => { if (event.target === event.currentTarget) setEditing(null); }}>
        <div className="stack"><button onClick={() => setEditing(null)}>关闭编辑</button>
          <ErrorBox error={edit.error} />
          {editing.line.status === 'SUBMITTED' && <p className="notice">保存后会出更改单，请通知对应档口按新内容准备。</p>}
          {editingMenu ? <ItemPicker key={`${editing.line.id}:${editing.line.revision}`} initial={editing.line}
            item={editing.line.status === 'SUBMITTED' ? { ...editingMenu, sold_out: false } : editingMenu} busy={edit.isPending}
            onAdd={(quantity, ids, notes, unitPrice) => edit.mutate({ quantity, ids, notes, unitPrice })} />
            : <p className="error">菜品已停售，当前无法修改。</p>}
        </div>
      </div>}
      {roundDetails && <div className="modal" role="dialog" aria-modal="true" aria-label="修改整单备注" onClick={(event) => { if (event.target === event.currentTarget) setRoundDetails(null); }}>
        <div className="card stack"><h2>订单 #{roundDetails.id} · 备注 / 标记</h2>
          <label>本轮备注<textarea maxLength={500} rows={3} value={roundNotes} onChange={(event) => setRoundNotes(event.target.value)} /></label>
          <label className="check"><input type="checkbox" checked={roundPaid} onChange={(event) => setRoundPaid(event.target.checked)} />本轮已付款（仅手动标记）</label>
          <small>不会生成收款记录，也不会重复下单。</small><ErrorBox error={saveRoundDetails.error} />
          <button className="primary" disabled={saveRoundDetails.isPending} onClick={() => saveRoundDetails.mutate()}>保存备注 / 标记</button>
          <button onClick={() => setRoundDetails(null)}>返回</button>
        </div>
      </div>}
      {cancelTarget && <div className="modal" role="dialog" aria-modal="true" aria-label="确认取消订单" onClick={(event) => { if (event.target === event.currentTarget) setCancelTarget(null); }}>
        <div className="card stack"><h2>{cancelTarget.kind === 'TABLE' ? `${bill.data?.table} · 取消整桌` : `取消 ${cancelTarget.line.quantity} × ${cancelTarget.line.name}`}</h2>
          <p>{cancelTarget.kind === 'TABLE' ? '取消全部未付款餐点和草稿，并释放桌台。' : '此项会从应付账单中移除。'}已下单的餐点会通知相关档口停止制作。</p>
          {bill.data?.has_prepaid_label && <p className="warning">此桌有先付款标记，请先处理已收款项。取消操作不会登记收款或退款。</p>}
          <label>取消原因<select value={cancelReason} onChange={(event) => setCancelReason(event.target.value)}>
            {['顾客取消','等候太久','点错餐','其他'].map((reason) => <option key={reason}>{reason}</option>)}
          </select></label>
          <ErrorBox error={cancelOrder.error} />
          <button className="primary" disabled={cancelOrder.isPending || !cancelReason.trim()} onClick={() => cancelOrder.mutate()}>
            {cancelTarget.kind === 'TABLE' ? '确认取消整桌' : '确认取消此项'}</button>
          <button onClick={() => setCancelTarget(null)}>返回</button>
        </div>
      </div>}
    </>
  );
}
