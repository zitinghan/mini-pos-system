import { fireEvent, render, screen } from '@testing-library/react';
import { expect, it, vi } from 'vitest';
import CustomItemForm from './CustomItemForm';

it('requires a valid manual price and multiplies quantity in sen', () => {
  const save = vi.fn();
  render(<CustomItemForm category="MAINS" busy={false} onSave={save} />);
  expect(screen.getByRole('button', { name:'加入自定义草稿' })).toBeDisabled();
  fireEvent.change(screen.getByLabelText('餐点名称'), { target:{value:'特别饭'} });
  fireEvent.change(screen.getByLabelText('单价 (RM)'), { target:{value:'8.75'} });
  fireEvent.change(screen.getByLabelText('制作档口'), { target:{value:'RICE'} });
  fireEvent.click(screen.getByRole('button', { name:'增加自定义数量' }));
  fireEvent.click(screen.getByRole('checkbox', { name:'打包' }));
  fireEvent.click(screen.getByRole('button', { name:'加入自定义草稿 · RM 17.50' }));
  expect(save).toHaveBeenCalledWith({name:'特别饭',unit_price:875,quantity:2,category_code:'MAINS',printer_group:'RICE',
    takeaway:true,notes:'',bottles_per_unit:0});
  fireEvent.change(screen.getByLabelText('单价 (RM)'), { target:{value:'1.234'} });
  expect(screen.getByRole('button', { name:/加入自定义草稿/ })).toBeDisabled();
});

it('routes drink categories contextually and tracks custom beer bottle packages', () => {
  const save = vi.fn();
  render(<CustomItemForm category="DRINKS" busy={false} onSave={save} />);
  expect(screen.getByLabelText('制作档口')).toHaveValue('BEVERAGE');
  fireEvent.change(screen.getByLabelText('分类'), { target:{value:'BEER'} });
  fireEvent.change(screen.getByLabelText('每份瓶数'), { target:{value:'3'} });
  fireEvent.change(screen.getByLabelText('餐点名称'), { target:{value:'其他啤酒'} });
  fireEvent.change(screen.getByLabelText('单价 (RM)'), { target:{value:'50'} });
  fireEvent.click(screen.getByRole('button', { name:'加入自定义草稿 · RM 50.00' }));
  expect(save.mock.calls[0][0].bottles_per_unit).toBe(3);
});

it('locks submitted routing while retaining editable custom names and prices', () => {
  render(<CustomItemForm category="MAINS" busy={false} onSave={vi.fn()} initial={{id:1,name:'特别饭',quantity:1,
    base_price:800,unit_price:800,line_total:800,status:'SUBMITTED',modifiers:[],is_custom:true,category_code:'MAINS',printer_group:'RICE'}} />);
  expect(screen.getByLabelText('制作档口')).toBeDisabled();
  expect(screen.getByLabelText('分类')).toBeDisabled();
  expect(screen.getByLabelText('餐点名称')).toBeEnabled();
  expect(screen.getByLabelText('单价 (RM)')).toHaveValue('8.00');
});
