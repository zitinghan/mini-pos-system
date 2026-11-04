import {describe,it,expect} from 'vitest';
import {parseSen,money} from './format';
describe('integer-sen money',()=>{
 it('parses exact decimals and rejects fractional sen',()=>{expect(parseSen('29')).toBe(2900);expect(parseSen('50.00')).toBe(5000);expect(parseSen('0.10')).toBe(10);expect(parseSen('8.001')).toBeNull();expect(parseSen('-1')).toBeNull();expect(parseSen('')).toBeNull();});
 it('formats the acceptance bill and change',()=>{expect(money(2900)).toBe('RM 29.00');expect(money(5000-2900)).toBe('RM 21.00');});
});
