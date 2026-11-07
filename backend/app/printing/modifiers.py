"""Keep neutral selections in snapshots while omitting redundant printed labels."""
NEUTRAL_NAMES = frozenset({'不加蛋', '普通', '堂食'})
REVERSALS = {'不加蛋': {'加蛋'}, '普通': {'加面', '大份'}, '堂食': {'打包'}}


def visible_modifiers(modifiers, previous=()):
    previous_names = {entry['name'] for entry in previous}
    return [entry for entry in modifiers if entry['name'] not in NEUTRAL_NAMES or entry.get('price', 0) != 0
        or REVERSALS.get(entry['name'], set()) & previous_names]
