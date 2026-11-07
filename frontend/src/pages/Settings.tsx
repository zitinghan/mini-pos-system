import { useEffect, useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { api } from '../services/api';
import type { MenuItem, Printer, User, Option } from '../services/types';
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

export default function Settings() {
  const client = useQueryClient();
  const [form, setForm] = useState<Printer | null>(null);
  const [name, setName] = useState('');
  const [pin, setPin] = useState('');
  const [role, setRole] = useState<'STAFF' | 'ADMIN'>('STAFF');
  const menu = useQuery({ queryKey: ['menu'], queryFn: () => api<MenuItem[]>('/menu') });
  const printer = useQuery({ queryKey: ['printer-config'], queryFn: () => api<Printer>('/printers/config') });
  const users = useQuery({ queryKey: ['users'], queryFn: () => api<User[]>('/users') });
  useEffect(() => { if (printer.data) setForm(printer.data); }, [printer.data]);
  const save = useMutation({ mutationFn: () => api('/printers/config', 'PUT', form), onSuccess: () => { void client.invalidateQueries({ queryKey: ['printer-config'] }); } });
  const test = useMutation({ mutationFn: () => api('/printers/test-print', 'POST') });
  const verify = useMutation({ mutationFn: (id: number) => api(`/menu/items/${id}/verify`, 'POST'), onSuccess: () => { void client.invalidateQueries({ queryKey: ['menu'] }); } });
  const create = useMutation({ mutationFn: () => api('/users', 'POST', { name, pin, role }), onSuccess: () => { setName(''); setPin(''); void client.invalidateQueries({ queryKey: ['users'] }); } });
  const change = <K extends keyof Printer>(key: K, value: Printer[K]) => setForm((previous) => previous ? { ...previous, [key]: value } : null);
  return <>
    <h1>管理设置</h1><ErrorBox error={menu.error || printer.error || users.error || verify.error} />
    <section className="card stack"><h2>菜单价格 (RM)</h2><small>仅影响新下单，历史账单保留原价。热 / 冰及啤酒包装均为独立定价。</small>
      {menu.data?.map((item) => <details key={item.id}><summary>{item.name} · {item.description || money(item.base_price)}</summary>
        {item.verification_required && <div className="warning"><p>{item.verification_note}</p><button disabled={verify.isPending} onClick={() => verify.mutate(item.id)}>已核实供应方式及价格</button></div>}
        {item.complimentary ? <p>白开水免费 · RM 0.00</p> : <>
          {!item.groups.some((group) => group.options.some((option) => option.unit_price != null)) && <PriceEditor id={item.id} name={item.name} price={item.base_price} />}
          {item.groups.filter((group) => group.minimum > 0).flatMap((group) => group.options.map((option) => <PriceEditor key={option.id} id={option.id} name={`${group.name} · ${option.name}${option.unit_price == null ? '（加价）' : '（单价）'}`} price={option.unit_price ?? option.price} option />))}
        </>}
        {item.groups.filter((group) => group.minimum === 0).map((group) => <section key={group.id}><h2>{group.name}</h2>{group.options.map((option) => <Customization key={option.id} option={option} peers={group.options} />)}</section>)}
      </details>)}
    </section>
    <section className="card stack"><h2>厨房 / 饮料打印机 · 58mm</h2>{!form ? <Loading /> : <form className="stack" onSubmit={(event) => { event.preventDefault(); save.mutate(); }}>
      <label>连接模式<select value={form.mode} onChange={(event) => change('mode', event.target.value as Printer['mode'])}><option value="mock">模拟打印机（开发）</option><option value="network">店内网络 ESC/POS</option></select></label>
      <label className="check"><input type="checkbox" checked={!!form.separate_stations} onChange={(event) => change('separate_stations', event.target.checked)} />厨房和饮料使用独立打印机</label>
      {!form.separate_stations && <small>同一张票按厨房 / 饮料分区，每个菜品只打印一次。</small>}
      {form.mode === 'mock' && <label>模拟结果<select value={form.simulation} onChange={(event) => change('simulation', event.target.value as Printer['simulation'])}><option value="success">成功发送</option><option value="connection_failure">连接失败（未发送）</option><option value="timeout">发送超时（结果不确定）</option><option value="uncertain">送达不确定</option></select></label>}
      {form.mode === 'network' && (form.separate_stations ? <>
        <label>厨房打印机 IP<input value={form.kitchen_host ?? ''} placeholder="192.168.1.200" onChange={(event) => change('kitchen_host', event.target.value)} /></label>
        <label>厨房 TCP 端口<input type="number" value={form.kitchen_port ?? 9100} onChange={(event) => change('kitchen_port', Number(event.target.value))} /></label>
        <label>饮料打印机 IP<input value={form.beverage_host ?? ''} placeholder="192.168.1.201" onChange={(event) => change('beverage_host', event.target.value)} /></label>
        <label>饮料 TCP 端口<input type="number" value={form.beverage_port ?? 9100} onChange={(event) => change('beverage_port', Number(event.target.value))} /></label>
      </> : <><label>打印机局域网 IP<input value={form.host} placeholder="192.168.1.200" onChange={(event) => change('host', event.target.value)} /></label><label>TCP 端口<input type="number" value={form.port} onChange={(event) => change('port', Number(event.target.value))} /></label></>)}
      <label>打印模式<select value={form.print_mode} onChange={(event) => change('print_mode', event.target.value as Printer['print_mode'])}><option value="raster">图片（推荐中文）</option><option value="text">文字（需要打印机支持）</option></select></label>
      <details><summary>硬件兼容设置</summary><div className="stack">
        <label>编码<input value={form.encoding} onChange={(event) => change('encoding', event.target.value)} /></label>
        <label>ESC/POS 配置名称<input value={form.profile} onChange={(event) => change('profile', event.target.value)} /></label>
        <label>图片指令<select value={form.raster_command} onChange={(event) => change('raster_command', event.target.value as Printer['raster_command'])}>{['bitImageRaster', 'graphics', 'bitImageColumn'].map((value) => <option key={value}>{value}</option>)}</select></label>
        <label>可打印宽度（像素）<input type="number" min={192} max={576} step={8} value={form.width} onChange={(event) => change('width', Number(event.target.value))} /></label>
        <label>打印后走纸行数<input type="number" min={0} max={10} value={form.feed} onChange={(event) => change('feed', Number(event.target.value))} /></label>
        <label className="check"><input type="checkbox" checked={form.cutter} onChange={(event) => change('cutter', event.target.checked)} />兼容自动切纸器</label>
      </div></details>
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
