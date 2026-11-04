import {fireEvent,render,screen} from '@testing-library/react';
import {describe,it,expect,vi} from 'vitest';
import {ItemPicker} from './Session';
import type {MenuItem} from '../services/types';
const item:MenuItem={id:1,name:'云吞面',base_price:800,groups:[{id:1,name:'酱汁',minimum:1,maximum:1,options:[{id:1,name:'黑酱',price:0,is_default:true},{id:2,name:'白酱',price:0,is_default:false}]},{id:2,name:'份量',minimum:1,maximum:1,options:[{id:3,name:'普通',price:0,is_default:true},{id:4,name:'加面',price:200,is_default:false}]}]};
describe('touch ordering',()=>{
 it('selects extra noodles and two portions for RM20',()=>{const add=vi.fn();render(<ItemPicker item={item} onAdd={add} busy={false}/>);fireEvent.click(screen.getByRole('button',{name:/加面/}));fireEvent.click(screen.getByRole('button',{name:'增加数量'}));fireEvent.click(screen.getByRole('button',{name:'加入草稿 · RM 20.00'}));expect(add).toHaveBeenCalledWith(2,[1,4]);});
 it('keeps one sauce selection and prevents repeated add while saving',()=>{render(<ItemPicker item={item} onAdd={vi.fn()} busy/>);fireEvent.click(screen.getByRole('button',{name:'白酱'}));expect(screen.getByRole('button',{name:'黑酱'})).toHaveAttribute('aria-pressed','false');expect(screen.getByRole('button',{name:'白酱'})).toHaveAttribute('aria-pressed','true');expect(screen.getByRole('button',{name:'正在保存…'})).toBeDisabled();});
});
