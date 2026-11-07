const neutralNames = new Set(['不加蛋', '普通', '堂食']);

export function visibleModifiers<T extends { name: string; price: number }>(modifiers: T[]): T[] {
  return modifiers.filter((modifier) => !neutralNames.has(modifier.name) || modifier.price !== 0);
}
