"""Versioned, idempotent menu installation; never rewrites submitted snapshots."""
from sqlalchemy import select
from app.database.db import transaction
from app.models.entities import RestaurantTable, MenuCategory, MenuItem, ModifierGroup, ModifierOption, MenuItemModifierGroup, PrinterConfiguration
from app.schemas.requests import PrinterSettings

CATEGORIES = [('MAINS', '主食', 'Mains', 'KITCHEN'), ('SNACKS', '小吃', 'Snacks & Sides', 'KITCHEN'),
              ('DRINKS', '饮料', 'Drinks', 'BEVERAGE'), ('BEER', '啤酒', 'Beer', 'BEVERAGE')]
DRINKS = [('KOPI_O', 'Kopi O', 230, 260), ('KOPI', 'Kopi', 250, 280), ('KOPI_C', 'Kopi C', 260, 290),
          ('WHITE_COFFEE', '白咖啡', 350, 380), ('TEH_O', 'Teh O', 230, 260), ('TEH', 'Teh', 250, 280),
          ('TEH_C', 'Teh C', 260, 290), ('MILO', 'Milo', 300, 330), ('MILO_MILK', 'Milo 奶', 330, 360),
          ('THREE_LAYER_TEA', '三色茶', 330, 360), ('MINERAL_WATER', '矿泉水', 180, 210),
          ('CORN', '玉米水', 180, 210), ('HERBAL_TEA', '凉茶', 180, 210), ('SOY', '豆奶', 200, 230),
          ('CANNED', '汽水 / 罐装', 300, 330)]
SNACKS = [('FRIED_WANTAN', '炸云吞', '10粒', 700), ('PORK_BALLS', '炸猪肉圆', '10粒', 700),
          ('FISH_BALLS', '炸鱼圆', '10粒', 700), ('SPRING_ROLLS', '炸春卷', '3条', 700),
          ('FRIES', '炸薯条', '1盘', 700), ('ANCHOVIES', '炸江鱼仔', '1盘', 700),
            ('BRAISED', '卤味拼盘', '卤肉 + 卤蛋 + 卤豆腐', 1500), ('WANTAN_SOUP', '云吞汤', '10粒', 800)]
BEERS = [('CARLSBERG', 'Carlsberg', 2200, 6000), ('TIGER', 'Tiger', 2100, 5700), ('GUINNESS', 'Guinness Stout', 2400, 6600)]
EXTRAS = ['不要青葱', '不要菜', '换成鱼圆', '加咖喱汁']
CUSTOM_ITEM_SKU = 'CUSTOM_ORDER_ITEM'


def seed():
    with transaction() as db:
        for number in range(1, 21):
            if not db.scalar(select(RestaurantTable).where(RestaurantTable.name == f'T{number:02d}')):
                db.add(RestaurantTable(name=f'T{number:02d}'))
        categories = {}
        for index, (code, name, english, station) in enumerate(CATEGORIES):
            category = db.scalar(select(MenuCategory).where(MenuCategory.code == code))
            if category is None:
                category = MenuCategory(code=code, name=name, english_name=english, printer_group=station, display_order=index)
                db.add(category)
                db.flush()
            categories[code] = category

        def install(sku, name, category, price, groups, aliases=(), description='', complimentary=False, verify=False,
                    printer_group=None, display_order=0):
            if db.scalar(select(MenuItem.id).where(MenuItem.sku == sku)) is not None:
                return  # Preserve administrator prices, enabled options and conflict rules.
            matches = list(db.scalars(select(MenuItem).where(MenuItem.name.in_([name, *aliases]), MenuItem.sku.is_(None)).order_by(MenuItem.id)))
            item = matches[0] if matches else MenuItem(name=name, category_id=categories[category].id, base_price=price)
            for duplicate in matches[1:]:
                duplicate.active = False
            item.name, item.sku, item.category_id = name, sku, categories[category].id
            item.base_price, item.description, item.complimentary = price, description, complimentary
            item.printer_group, item.display_order = printer_group, display_order
            item.verification_required = verify
            item.verification_note = '请在营业前核实瓶装水 / 罐装饮料的热、冰供应方式和价格。' if verify else ''
            db.add(item)
            db.flush()
            for position, (group_name, minimum, maximum, options) in enumerate(groups):
                group = db.scalar(select(ModifierGroup).join(MenuItemModifierGroup, MenuItemModifierGroup.group_id == ModifierGroup.id)
                                  .where(MenuItemModifierGroup.item_id == item.id, ModifierGroup.name == group_name))
                if group is None:
                    group = ModifierGroup(name=group_name, minimum=minimum, maximum=maximum, display_order=position)
                    db.add(group)
                    db.flush()
                    db.add(MenuItemModifierGroup(item_id=item.id, group_id=group.id))
                for option_position, definition in enumerate(options):
                    option_name, surcharge, unit_price, bottles = definition
                    option = db.scalar(select(ModifierOption).where(ModifierOption.group_id == group.id, ModifierOption.name == option_name))
                    if option is None:
                        option = ModifierOption(group_id=group.id, name=option_name)
                        db.add(option)
                    option.price, option.unit_price, option.bottles = surcharge, unit_price, bottles
                    option.is_default = minimum > 0 and option_position == 0
                    option.display_order = option_position

        def choices(name, values):
            return (name, 1, 1, [(label, price, None, 0) for label, price in values])

        extras = ('免费定制', 0, 4, [(name, 0, None, 0) for name in EXTRAS])
        install('WANTAN_MEE', '云吞面', 'MAINS', 800, [choices('酱汁', [('黑酱', 0), ('白酱', 0), ('红酱', 0), ('汤', 0)]),
                choices('辣度', [('不辣', 0), ('辣', 0)]), choices('份量', [('普通', 0), ('加面', 200)]), extras])
        install('MEE_HOON_KUEH', '面粉粿', 'MAINS', 800, [choices('做法', [('汤', 0), ('干', 0)]), choices('鸡蛋', [('不加蛋', 0), ('加蛋', 100)]), extras], aliases=('面粉糕',))
        install('CURRY_RICE', '海南咖喱饭', 'MAINS', 800, [choices('份量', [('普通', 0), ('大份', 200)]), extras], aliases=('咖喱卤肉饭',), printer_group='RICE')
        for sku, name in [('BRAISED_PORK_RICE', '卤肉饭'), ('PLAIN_CURRY_RICE', '咖喱饭')]:
            install(sku, name, 'MAINS', 800, [choices('份量', [('普通', 0), ('大份', 200)]), extras], printer_group='RICE')
        for priority, (sku, name) in enumerate([('BRAISED_PORK_SIDE', '卤肉'), ('CURRY_CHICKEN_SIDE', '咖喱鸡')]):
            install(sku, name, 'SNACKS', 800, [], printer_group='RICE', display_order=-20 + priority)
        for sku, name, portion, price in SNACKS:
            install(sku, name, 'SNACKS', price, [], description=portion)
        for sku, name, hot, iced in DRINKS:
            install(sku, name, 'DRINKS', hot, [('温度', 1, 1, [('热 HOT', 0, hot, 0), ('冰 ICED', 0, iced, 0)])], verify=sku in ('MINERAL_WATER', 'CANNED'))
        install('PLAIN_WATER', '白开水', 'DRINKS', 0, [('温度', 1, 1, [('冷', 0, 0, 0), ('热', 0, 0, 0)])], complimentary=True)
        for sku, name, single, triple in BEERS:
            install(sku, name, 'BEER', single, [('包装', 1, 1, [('单瓶', 0, single, 1), ('3瓶', 0, triple, 3)])])
        if db.get(PrinterConfiguration, 1) is None:
            db.add(PrinterConfiguration(id=1, config=PrinterSettings().model_dump()))

        def ensure_optional_choices(item, name, position, options, incompatible_with=(), prices=None):
            group = db.scalar(select(ModifierGroup).join(MenuItemModifierGroup, MenuItemModifierGroup.group_id == ModifierGroup.id)
                .where(MenuItemModifierGroup.item_id == item.id, ModifierGroup.name == name))
            if group is None:
                group = ModifierGroup(name=name, minimum=0, maximum=1, display_order=position)
                db.add(group)
                db.flush()
                db.add(MenuItemModifierGroup(item_id=item.id, group_id=group.id))
            for index, (option_name, default) in enumerate(options):
                if db.scalar(select(ModifierOption.id).where(ModifierOption.group_id == group.id, ModifierOption.name == option_name)) is None:
                    db.add(ModifierOption(group_id=group.id, name=option_name, price=(prices or {}).get(option_name, 0), is_default=default,
                        display_order=index, incompatible_with=list(incompatible_with)))
            db.flush()

        # Existing products also receive new groups; never overwrite operator edits or submitted snapshots.
        prepared_drinks = {sku for sku, *_ in DRINKS} - {'MINERAL_WATER', 'CANNED'}
        for item in db.scalars(select(MenuItem).order_by(MenuItem.id)):
            if item.sku == CUSTOM_ITEM_SKU:
                continue
            ensure_optional_choices(item, '用餐方式', 100, [('堂食', True), ('打包', False)])
            if item.sku == 'WANTAN_MEE':
                sauce = db.scalar(select(ModifierGroup).join(MenuItemModifierGroup, MenuItemModifierGroup.group_id == ModifierGroup.id)
                    .where(MenuItemModifierGroup.item_id == item.id, ModifierGroup.name == '酱汁'))
                if sauce is not None:
                    options = list(db.scalars(select(ModifierOption).where(ModifierOption.group_id == sauce.id)))
                    if not any(option.name == '汤' for option in options):
                        db.add(ModifierOption(group_id=sauce.id, name='汤', price=0, is_default=False,
                            display_order=max((option.display_order for option in options), default=-1) + 1))
            if item.sku == 'MEE_HOON_KUEH':
                ensure_optional_choices(item, '份量', 10, [('普通', True), ('大份', False)], prices={'大份': 200})
            if item.sku == 'CANNED':
                ensure_optional_choices(item, '品牌 / 口味', 20, [(name, False) for name in
                    ['Sprite', 'Coke', 'Fanta', '100 PLUS', '菊花茶', '7UP', 'Passion Fruit']])
            if item.sku in prepared_drinks:
                ensure_optional_choices(item, '甜度', 80, [('Kosong（不加糖）', False), ('Siu Dai（少甜）', False)])
                ensure_optional_choices(item, '浓度', 90, [('Kao（加浓）', False)])
                hot_ids = list(db.scalars(select(ModifierOption.id).join(ModifierGroup, ModifierGroup.id == ModifierOption.group_id)
                    .join(MenuItemModifierGroup, MenuItemModifierGroup.group_id == ModifierGroup.id)
                    .where(MenuItemModifierGroup.item_id == item.id, ModifierGroup.name == '温度', ModifierOption.name == '热 HOT')))
                ensure_optional_choices(item, '冰量', 95, [('少冰 Less Ice', False), ('去冰 No Ice', False)], hot_ids)
        # One hidden reference preserves existing order-item foreign keys.
        # Custom names/prices live in order snapshots, never in the public menu.
        if db.scalar(select(MenuItem.id).where(MenuItem.sku == CUSTOM_ITEM_SKU)) is None:
            db.add(MenuItem(sku=CUSTOM_ITEM_SKU, name='自定义餐点（内部）', category_id=categories['MAINS'].id,
                base_price=0, active=False, display_order=10000))
