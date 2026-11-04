from sqlalchemy import select
from app.database.db import transaction
from app.models.entities import RestaurantTable, MenuCategory, MenuItem, ModifierGroup, ModifierOption, MenuItemModifierGroup, PrinterConfiguration
from app.schemas.requests import PrinterSettings


def seed():
    with transaction() as db:
        if db.scalar(select(RestaurantTable.id).limit(1)) is not None:
            return
        db.add_all(RestaurantTable(name=f'T{i:02d}') for i in range(1, 16))
        definitions = [
            ('云吞面', [('酱汁', [('黑酱', 0), ('白酱', 0), ('红酱', 0)]), ('辣度', [('不辣', 0), ('辣', 0)]), ('份量', [('普通', 0), ('加面', 200)])]),
            ('面粉糕', [('做法', [('汤', 0), ('干', 0)]), ('鸡蛋', [('不加蛋', 0), ('加蛋', 100)])]),
            ('咖喱卤肉饭', [('份量', [('普通', 0), ('大份', 200)])]),
        ]
        for index, (name, groups) in enumerate(definitions):
            category = MenuCategory(name=name, display_order=index)
            db.add(category)
            db.flush()
            item = MenuItem(category_id=category.id, name=name, base_price=800)
            db.add(item)
            db.flush()
            for order, (group_name, options) in enumerate(groups):
                group = ModifierGroup(name=group_name, display_order=order)
                db.add(group)
                db.flush()
                db.add(MenuItemModifierGroup(item_id=item.id, group_id=group.id))
                for position, (option_name, price) in enumerate(options):
                    db.add(ModifierOption(group_id=group.id, name=option_name, price=price, is_default=position == 0, display_order=position))
        db.add(PrinterConfiguration(id=1, config=PrinterSettings().model_dump()))
