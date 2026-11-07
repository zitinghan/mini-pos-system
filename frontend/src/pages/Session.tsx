import { useEffect, useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { api, requestKey, clearKey } from '../services/api';
import type { MenuItem, Batch, Bill, CategoryCode } from '../services/types';
import { useAuth } from '../stores/auth';
import { useUI } from '../stores/ui';
import { money } from '../utils/format';
import { label } from '../utils/i18n';
import { Lines, ErrorBox, Loading, ConfirmButton } from '../components/Common';

interface PickerProps {
  item: MenuItem;
  onAdd: (quantity: number, ids: number[], notes?: string) => void;
  busy: boolean;
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

export function ItemPicker({ item, onAdd, busy }: PickerProps) {
  const [selected, setSelected] = useState<number[]>(
    item.groups.flatMap((group) => group.options.filter((option) => option.is_default && option.enabled !== false)
      .map((option) => option.id)),
  );
  const [quantity, setQuantity] = useState(1);
  const [notes, setNotes] = useState('');
  const allOptions = item.groups.flatMap((group) => group.options);
  const selectedOptions = allOptions.filter((option) => selected.includes(option.id));
  const variant = selectedOptions.find((option) => option.unit_price != null);
  const price = (variant?.unit_price ?? item.base_price) + selectedOptions.reduce((sum, option) => sum + option.price, 0);
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
      {item.groups.map((group) => (
        <fieldset key={group.id}>
          <legend>{group.name} <small>{group.minimum > 0 ? '必选' : '可选'}</small></legend>
          <div className="option-grid">
            {group.options.filter((option) => option.enabled !== false).map((option) => (
              <button type="button" key={option.id}
                disabled={!selected.includes(option.id) && selectedOptions.some((entry) =>
                  entry.incompatible_with?.includes(option.id) || option.incompatible_with?.includes(entry.id))}
                aria-pressed={selected.includes(option.id)}
                className={selected.includes(option.id) ? 'selected' : ''}
                onClick={() => setSelected((previous) => {
                  if (group.maximum === 1) {
                    if (group.minimum === 0 && previous.includes(option.id)) {
                      return previous.filter((id) => id !== option.id);
                    }
                    return [...previous.filter((id) => !group.options.some((entry) => entry.id === id)), option.id];
                  }
                  return previous.includes(option.id)
                    ? previous.filter((id) => id !== option.id) : [...previous, option.id];
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
        onClick={() => notes.trim() ? onAdd(quantity, selected, notes.trim()) : onAdd(quantity, selected)}>
        {item.sold_out ? 'SOLD OUT · 已售罄' : busy ? '正在保存…' : `加入草稿 · ${money(price * quantity)}`}
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
  const [category, setCategory] = useState<CategoryCode>('MAINS');
  const [error, setError] = useState<unknown>(null);
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
      const scope = `submit:${ownDraft.id}`;
      const result = await api<{ batch_id: number; print_job_id: number }>(
        `/order-batches/${ownDraft.id}/submit`, 'POST', undefined, requestKey(scope),
      );
      clearKey(scope);
      return result;
    },
    onSuccess: (result) => {
      refresh();
      useUI.getState().setNotice(
        `订单 #${result.batch_id} 已保存；厨房打印任务 #${result.print_job_id} 已排队。请在订单页查看发送状态。`,
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

  if (bill.isPending || batches.isPending || menu.isPending) {
    return <><Loading /><ErrorBox error={bill.error || batches.error || menu.error} /></>;
  }
  const active = bill.data?.status === 'OCCUPIED';
  const cashier = user?.role === 'ADMIN' && ['OCCUPIED', 'PAYMENT_PENDING'].includes(bill.data?.status ?? '');

  return (
    <>
      <Link className="back" to="/">← 返回桌台</Link>
      <div className="page-title">
        <div><p className="eyebrow">{label(bill.data?.status ?? '')}</p><h1>{bill.data?.table} 点餐</h1></div>
        <strong>{money(bill.data?.total ?? 0)}</strong>
      </div>
      <ErrorBox error={error || bill.error || batches.error || menu.error} />
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
            <MenuItemButton key={item.id} item={item} selected={chosen?.id === item.id} onSelect={setChosen} />
          ))}
        </div>
        {currentChosen && <ItemPicker key={currentChosen.id} item={currentChosen} busy={add.isPending}
          onAdd={(quantity, ids, notes) => add.mutate({ quantity, ids, notes })} />}
      </>}
      {ownDraft && (
        <section className="card stack">
          <div className="row spread"><h2>当前草稿</h2><span className="pill">未送厨房</span></div>
          <Lines items={drafts} />
          {drafts.map((item) => (
            <button key={item.id} className="quiet" disabled={remove.isPending}
              onClick={() => remove.mutate(item.id)}>移除 {item.quantity} × {item.name}</button>
          ))}
          <strong>预计 {money(drafts.reduce((sum, item) => sum + item.line_total, 0))}</strong>
          <small>价格以确认下单时菜单为准。</small>
          {unavailableDrafts.length > 0 && <p className="warning" role="alert">{unavailableDrafts.map((item) => item.name).join('、')} 已售罄，请先移除或等待恢复供应。</p>}
          <button className="primary" disabled={!active || !drafts.length || unavailableDrafts.length > 0 || submit.isPending || add.isPending}
            onClick={() => submit.mutate()}>
            {submit.isPending ? '正在确认…' : '确认下单 / 送厨房'}
          </button>
          <ConfirmButton disabled={discard.isPending} onConfirm={() => discard.mutate()}>丢弃此草稿</ConfirmButton>
        </section>
      )}
      <section className="card stack">
        <h2>已下单 · 桌台账单</h2>
        {batches.data?.filter((batch) => batch.status !== 'DRAFT').map((batch) => (
          <div key={batch.id}>
            <p className="batch-heading">#{batch.id} · {label(batch.status)}</p>
            <Lines items={batch.items} />
          </div>
        ))}
        {!bill.data?.items.length && <p className="muted">尚未确认任何菜品。</p>}
        <div className="row spread"><h2>合计</h2><h2>{money(bill.data?.total ?? 0)}</h2></div>
        {cashier && <button className="primary" disabled={checkout.isPending || !bill.data?.item_count}
          onClick={() => checkout.mutate()}>查看账单 / 收款</button>}
        {cashier && !bill.data?.item_count && (
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
    </>
  );
}
