import { useEffect, useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { api } from '../services/api';
import type { MenuItem, Printer, User, Option, Promotion, CategoryCode } from '../services/types';
import { money, parseSen } from '../utils/format';
import { ErrorBox, Loading } from '../components/Common';

function PriceEditor({ id, price, name, option = false }: { id: number; price: number; name: string; option?: boolean }) {
  const [value, setValue] = useState((price / 100).toFixed(2));
  const client = useQueryClient();
  useEffect(() => setValue((price / 100).toFixed(2)), [price]);
  const update = useMutation({ mutationFn: () => api(`/menu/${option ? 'options' : 'items'}/${id}`, 'PATCH', { price: parseSen(value) }), onSuccess: () => { void client.invalidateQueries({ queryKey: ['menu'] }); } });
  return <form className="price-editor" onSubmit={(event) => { event.preventDefault(); update.mutate(); }}>
    <label>{name}<input aria-label={`${name}价格`} inputMode="decimal" value={value} onChange={(event) => setValue(event.target.value)} /></label>
    <button disabled={update.isPending || parseSen(value) === null}>保存</button><ErrorBox error={update.error} />{update.isSuccess && <small role="status">已保存</small>}
  </form>;
}

function Customization({ option, peers }: { option: Option; peers: Option[] }) {
  const client = useQueryClient();
  const [enabled, setEnabled] = useState(option.enabled !== false);
  const [conflicts, setConflicts] = useState<number[]>(option.incompatible_with ?? []);
  const save = useMutation({ mutationFn: () => api(`/menu/options/${option.id}/configuration`, 'PATCH', { enabled, incompatible_with: conflicts }), onSuccess: () => { void client.invalidateQueries({ queryKey: ['menu'] }); } });
  return <form className="customization" onSubmit={(event) => { event.preventDefault(); save.mutate(); }}>
    <label className="check"><input type="checkbox" checked={enabled} onChange={(event) => setEnabled(event.target.checked)} />{option.name} · 免费</label>
    <small>不可同时选择：</small><div className="option-grid">{peers.filter((peer) => peer.id !== option.id).map((peer) => <button type="button" key={peer.id} aria-pressed={conflicts.includes(peer.id)} onClick={() => setConflicts((previous) => previous.includes(peer.id) ? previous.filter((id) => id !== peer.id) : [...previous, peer.id])}>{peer.name}</button>)}</div>
    <button disabled={save.isPending}>保存定制规则</button><ErrorBox error={save.error} />{save.isSuccess && <small role="status">已保存</small>}
  </form>;
}

export function AvailabilityButton({ item, pending, onToggle }: { item: MenuItem; pending: boolean; onToggle: () => void }) {
  return <button type="button" className={item.sold_out ? 'restore-stock' : 'quiet'} disabled={pending}
    aria-label={`${item.name} · ${item.sold_out ? '恢复供应' : '标记售罄'}`} onClick={onToggle}>
    {item.sold_out ? '恢复供应' : '标记售罄'}
  </button>;
}

export default function Settings() {
  const client = useQueryClient();
  const [form, setForm] = useState<Printer | null>(null);
  const [name, setName] = useState('');
  const [pin, setPin] = useState('');
  const [role, setRole] = useState<'STAFF' | 'ADMIN'>('STAFF');
  const [stockCategory, setStockCategory] = useState<CategoryCode>('MAINS');
  const menu = useQuery({ queryKey: ['menu'], queryFn: () => api<MenuItem[]>('/menu'), refetchInterval: 4000 });
  const promotions = useQuery({ queryKey: ['menu-promotions'], queryFn: () => api<Promotion[]>('/menu/promotions'), refetchInterval: 15000 });
  const printer = useQuery({ queryKey: ['printer-config'], queryFn: () => api<Printer>('/printers/config') });
  const windowsPrinters = useQuery({ queryKey: ['windows-printers'], queryFn: () => api<{printers:string[]}>('/printers/windows') });
  const users = useQuery({ queryKey: ['users'], queryFn: () => api<User[]>('/users') });
  useEffect(() => { if (printer.data) setForm(printer.data); }, [printer.data]);
  const save = useMutation({ mutationFn: () => api('/printers/config', 'PUT', form), onSuccess: () => { void client.invalidateQueries({ queryKey: ['printer-config'] }); } });
  const test = useMutation({ mutationFn: () => api('/printers/test-print', 'POST') });
  const verify = useMutation({ mutationFn: (id: number) => api(`/menu/items/${id}/verify`, 'POST'), onSuccess: () => { void client.invalidateQueries({ queryKey: ['menu'] }); } });
  const availability = useMutation({
    mutationFn: ({ id, soldOut }: { id: number; soldOut: boolean }) => api(`/menu/items/${id}/availability`, 'PATCH', { sold_out: soldOut }),
    onSuccess: () => { void client.invalidateQueries({ queryKey: ['menu'] }); },
  });
  const create = useMutation({ mutationFn: () => api('/users', 'POST', { name, pin, role }), onSuccess: () => { setName(''); setPin(''); void client.invalidateQueries({ queryKey: ['users'] }); } });
  const change = <K extends keyof Printer>(key: K, value: Printer[K]) => setForm((previous) => previous ? { ...previous, [key]: value } : null);
  return <>
    <h1>管理设置</h1><ErrorBox error={menu.error || printer.error || users.error || verify.error || availability.error || promotions.error} />
    <section className="card stack"><h2>售罄管理</h2><small>售罄会同步到其他员工手机，暂时禁止新增及提交该项目；已下单账单保留。</small>
      <div className="category-tabs" role="group" aria-label="供应分类">
        {([['MAINS', '主食'], ['SNACKS', '小吃'], ['DRINKS', '饮料'], ['BEER', '啤酒']] as const).map(([code, name]) =>
          <button key={code} aria-pressed={stockCategory === code} onClick={() => setStockCategory(code)}>{name}</button>)}
      </div>
      {menu.data?.filter((item) => (item.category_code ?? 'MAINS') === stockCategory).map((item) => <div className="line stock-row" key={item.id}>
        <div><strong>{item.name}</strong><small>{item.sold_out ? 'SOLD OUT · 已售罄' : '供应中'}</small></div>
        <AvailabilityButton item={item} pending={availability.isPending} onToggle={() => availability.mutate({ id: item.id, soldOut: !item.sold_out })} />
      </div>)}
    </section>
    {promotions.data?.map((promotion) => <section className="card stack" key={promotion.id}>
      <h2>{promotion.name} · {money(promotion.unit_price)}</h2>
      <p>{promotion.starts_on} 至 {promotion.ends_on}（含当天，马来西亚时间） · {promotion.is_active ? '进行中' : '未生效 / 已结束'}</p>
      <p>{promotion.skus.map((sku) => menu.data?.find((item) => item.sku === sku)?.name ?? sku).join('、')} · 热 / 冷同价</p>
      <small>常规价格保持不变，活动结束后自动恢复。白咖啡和三色茶不参与本次优惠。</small>
    </section>)}
    <section className="card stack"><h2>菜单价格 (RM)</h2><small>仅影响新下单，历史账单保留原价。热 / 冰及啤酒包装均为独立定价。</small>
      {menu.data?.map((item) => <details key={item.id}><summary>{item.name} · {item.description || money(item.regular_base_price ?? item.base_price)}</summary>
        {item.promotion && <p className="promotion">当前优惠 {money(item.promotion.unit_price)}，以下编辑的是到期后使用的常规价格。</p>}
        {item.verification_required && <div className="warning"><p>{item.verification_note}</p><button disabled={verify.isPending} onClick={() => verify.mutate(item.id)}>已核实供应方式及价格</button></div>}
        {item.complimentary ? <p>白开水免费 · RM 0.00</p> : <>
          {!item.groups.some((group) => group.options.some((option) => option.unit_price != null)) && <PriceEditor id={item.id} name={item.name} price={item.regular_base_price ?? item.base_price} />}
          {item.groups.filter((group) => group.minimum > 0).flatMap((group) => group.options.map((option) => <PriceEditor key={option.id} id={option.id} name={`${group.name} · ${option.name}${option.unit_price == null ? '（加价）' : '（单价）'}`} price={option.regular_unit_price ?? option.unit_price ?? option.price} option />))}
        </>}
        {item.groups.filter((group) => group.minimum === 0).map((group) => <section key={group.id}><h2>{group.name}</h2>{group.options.map((option) => <Customization key={option.id} option={option} peers={group.options} />)}</section>)}
      </details>)}
    </section>
    <section className="card stack"><h2>面档 / 饭档 / 饮料档打印机</h2>{!form ? <Loading /> : <form className="stack" onSubmit={(event) => { event.preventDefault(); save.mutate(); }}>
      <label>连接模式<select value={form.mode} onChange={(event) => change('mode', event.target.value as Printer['mode'])}><option value="mock">模拟打印机（开发）</option><option value="network">店内网络 ESC/POS</option></select></label>
      <label className="check"><input type="checkbox" checked={!!form.separate_stations} onChange={(event) => change('separate_stations', event.target.checked)} />面档、饭档和饮料档使用独立打印机</label>
      {!form.separate_stations && <small>同一台打印机分开打印面档单、饭档单、饮料单；没有点单的档口不出单，每项只打印一次。</small>}
      {form.mode === 'mock' && <label>模拟结果<select value={form.simulation} onChange={(event) => change('simulation', event.target.value as Printer['simulation'])}><option value="success">成功发送</option><option value="connection_failure">连接失败（未发送）</option><option value="timeout">发送超时（结果不确定）</option><option value="uncertain">送达不确定</option></select></label>}
      {form.mode === 'network' && (form.separate_stations ? <>
        <label>面档打印机 IP<input value={form.kitchen_host ?? ''} placeholder="192.168.1.200" onChange={(event) => change('kitchen_host', event.target.value)} /></label>
        <label>面档 TCP 端口<input type="number" value={form.kitchen_port ?? 9100} onChange={(event) => change('kitchen_port', Number(event.target.value))} /></label>
        <label>饭档打印机 IP<input value={form.rice_host ?? ''} placeholder="留空使用面档打印机" onChange={(event) => change('rice_host', event.target.value)} /></label>
        <label>饭档 TCP 端口<input type="number" value={form.rice_port ?? 9100} onChange={(event) => change('rice_port', Number(event.target.value))} /></label>
        <label>饮料打印机 IP<input value={form.beverage_host ?? ''} placeholder="192.168.1.201" onChange={(event) => change('beverage_host', event.target.value)} /></label>
        <label>饮料 TCP 端口<input type="number" value={form.beverage_port ?? 9100} onChange={(event) => change('beverage_port', Number(event.target.value))} /></label>
      </> : <><label>打印机局域网 IP<input value={form.host} placeholder="192.168.1.200" onChange={(event) => change('host', event.target.value)} /></label><label>TCP 端口<input type="number" value={form.port} onChange={(event) => change('port', Number(event.target.value))} /></label></>)}
      <label>打印模式<select value={form.print_mode} onChange={(event) => change('print_mode', event.target.value as Printer['print_mode'])}><option value="raster">图片（推荐中文）</option><option value="text">文字（需要打印机支持）</option></select></label>
      <div><strong>制作单纸宽</strong><div className="option-grid">
        {[{ width: 384, name: '58mm / 384 dots' }, { width: 576, name: '80mm / 576 dots' }].map((paper) => <button type="button" key={paper.width} aria-pressed={form.width === paper.width} className={form.width === paper.width ? 'selected' : ''} onClick={() => setForm({ ...form, width: paper.width, print_mode: 'raster' })}>{paper.name}</button>)}
      </div><small>选择纸宽会使用图片打印，让中文和备注按整张纸的可打印宽度换行。商品及选项保持大字。</small></div>
      <details><summary>硬件兼容设置</summary><div className="stack">
        <label>编码<input value={form.encoding} onChange={(event) => change('encoding', event.target.value)} /></label>
        <label>ESC/POS 配置名称<input value={form.profile} onChange={(event) => change('profile', event.target.value)} /></label>
        <label>图片指令<select value={form.raster_command} onChange={(event) => change('raster_command', event.target.value as Printer['raster_command'])}>{['bitImageRaster', 'graphics', 'bitImageColumn'].map((value) => <option key={value}>{value}</option>)}</select></label>
        <label>可打印宽度（像素）<input type="number" min={192} max={576} step={8} value={form.width} onChange={(event) => change('width', Number(event.target.value))} /></label>
        <label>打印后走纸行数<input type="number" min={0} max={10} value={form.feed} onChange={(event) => change('feed', Number(event.target.value))} /></label>
        <label className="check"><input type="checkbox" checked={form.cutter} onChange={(event) => change('cutter', event.target.checked)} />兼容自动切纸器</label>
      </div></details>
      <h2>收银收据打印机（独立）</h2>
      <small>成功收款并清台后自动打印整桌收据，不发送到厨房打印机。中文使用图片输出。</small>
      <label>收据连接模式<select value={form.receipt_mode ?? 'mock'} onChange={(event) => change('receipt_mode', event.target.value as Printer['receipt_mode'])}>
        <option value="mock">只生成预览（不打印）</option><option value="windows">Windows USB 热敏打印机</option><option value="network">收银网络打印机</option>
      </select></label>
      {form.receipt_mode === 'windows' && <>
        <label>Windows 收银打印机<select value={form.receipt_printer_name ?? ''} onChange={(event) => change('receipt_printer_name', event.target.value)}><option value="">请选择已安装的 ESC/POS 热敏打印机</option>{windowsPrinters.data?.printers.map((name) => <option key={name} value={name}>{name}</option>)}</select></label>
        <ErrorBox error={windowsPrinters.error} /><small>先在主机安装驱动并接好 USB；例如 POS-80C。换电脑后需重新选择该电脑的打印队列。</small>
      </>}
      {form.receipt_mode === 'network' && <>
        <label>收银打印机 IP<input value={form.receipt_host ?? ''} placeholder="192.168.1.202" onChange={(event) => change('receipt_host', event.target.value)} /></label>
        <label>收银 TCP 端口<input type="number" min={1} max={65535} value={form.receipt_port ?? 9100} onChange={(event) => change('receipt_port', Number(event.target.value))} /></label>
      </>}
      <label>收据纸宽<select value={form.receipt_paper_mm ?? ((form.receipt_width ?? 384) >= 500 ? 80 : 58)} onChange={(event) => setForm({ ...form, receipt_paper_mm: Number(event.target.value), receipt_width: Number(event.target.value) === 80 ? 576 : 384 })}><option value={55}>55mm / 384 dots</option><option value={58}>58mm / 384 dots</option><option value={80}>80mm / 576 dots</option></select></label>
      <label className="check"><input type="checkbox" checked={!!form.receipt_cutter} onChange={(event) => change('receipt_cutter', event.target.checked)} />收据自动切纸（仅支持的机型）</label>
      <ErrorBox error={save.error || test.error} />{save.isSuccess && <p role="status">设置已保存</p>}{test.isSuccess && <p role="status">测试任务已排队，请到订单页检查结果。</p>}
      <button className="primary" disabled={save.isPending}>保存打印设置</button><button type="button" disabled={test.isPending} onClick={() => test.mutate()}>用已保存配置打印测试单</button>
    </form>}</section>
    <section className="card stack"><h2>员工账户</h2>{users.data?.map((user) => <div className="row spread" key={user.id}><strong>{user.name}</strong><span>{user.role === 'ADMIN' ? '管理员 / 收银员' : '点餐员工'}</span></div>)}
      <form className="stack" onSubmit={(event) => { event.preventDefault(); create.mutate(); }}>
        <label>新员工名称<input required maxLength={80} value={name} onChange={(event) => setName(event.target.value)} /></label>
        <label>6–12 位数字 PIN<input required type="password" inputMode="numeric" pattern="[0-9]{6,12}" value={pin} onChange={(event) => setPin(event.target.value)} /></label>
        <label>角色<select value={role} onChange={(event) => setRole(event.target.value as 'STAFF' | 'ADMIN')}><option value="STAFF">点餐员工</option><option value="ADMIN">管理员 / 收银员</option></select></label>
        <ErrorBox error={create.error} /><button disabled={create.isPending}>创建员工账户</button>
      </form>
    </section>
  </>;
}
