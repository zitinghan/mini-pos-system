from datetime import datetime
from zoneinfo import ZoneInfo
from PIL import Image, ImageDraw, ImageFont
from app.core.config import FONT_PATH
from app.printing.stations import STATIONS
from app.printing.modifiers import visible_modifiers


def ticket_lines(ticket, reprint=False):
    if ticket.get('kind') == 'RECEIPT':
        return receipt_lines(ticket, reprint)
    lines = []
    if reprint:
        lines.append(('REPRINT / 重印', 25))
    lines.append((ticket.get('restaurant', '可可·南洋咖啡店'), 32))
    lines.append((f"桌号 {ticket['table']}", 48))
    number = ticket.get('ticket_number', ticket.get('batch_id', 'TEST'))
    lines.append((f"票号 #{str(number).zfill(6)}", 22))
    lines.append((f"整桌记录 #{ticket['session_id']}" if ticket.get('scope') == 'TABLE' else f"订单 #{ticket.get('batch_id', 'TEST')}", 22))
    order_type = 'REPRINT' if reprint else ticket.get('order_type', 'NEW')
    lines.append((f"类型 {order_type}", 25))
    timestamp = datetime.fromisoformat(ticket['time']).astimezone(ZoneInfo('Asia/Kuala_Lumpur'))
    lines.append((timestamp.strftime('%d/%m %H:%M'), 20))
    if ticket.get('order_type') == 'NOTE':
        lines.extend([('备注 / 标记更新', 40), ('只更新提示，请勿重复制作', 30),
            (dict(STATIONS).get(ticket.get('station'), ''), 30)])
        if ticket.get('note_scope') == 'TABLE':
            lines.append((f"整桌备注 {ticket.get('table_notes') or '（已清除）'}", 36))
        else:
            lines.append((f"本轮备注 {ticket.get('notes') or '（已清除）'}", 36))
            lines.append(('本轮已付款（手动标记）' if ticket.get('prepaid_label') else '本轮未标记先付款', 36))
        return lines
    if ticket.get('prepaid_label'):
        lines.append(('已付款（手动标记）', 36))
    if ticket.get('table_notes'):
        lines.append((f"整桌备注 {ticket['table_notes']}", 36))
    if ticket.get('notes'):
        lines.append((f"整单备注 {ticket['notes']}", 36))
    if ticket.get('order_type') == 'UPDATE':
        lines.extend([('更改单 / UPDATE', 40), ('请用更改后内容替换旧内容', 30)])
        lines.append((f"更改记录 #{ticket['change_ref']}", 22))
    if ticket.get('order_type') == 'CANCEL':
        lines.extend([('取消单 / CANCEL', 48), ('停止制作 / 不要出餐', 36), (f"原因 {ticket.get('reason', '顾客取消')}", 36)])
    total = 0
    for station, label in STATIONS:
        items = [item for item in ticket['items'] if item.get('printer_group', 'KITCHEN') == station]
        if not items:
            continue
        lines.append((f'----- {label} -----', 30))
        previous = [item for item in ticket.get('previous_items', []) if item.get('printer_group', 'KITCHEN') == station]
        if previous:
            lines.append(('原内容（作废）', 36))
            for item in previous:
                lines.append((f"{item['quantity']} x {item['name']}", 48))
                if item.get('description'):
                    lines.append((f"  {item['description']}", 36))
                lines.extend((f"  {entry['name']}", 48) for entry in visible_modifiers(item['modifiers']))
                if item.get('notes'):
                    lines.append((f"备注 {item['notes']}", 36))
            lines.append(('改为以下内容', 36))
        for item in items:
            lines.append(('------------------------', 20))
            lines.append((f"{item['quantity']} x {item['name']}", 48))
            total += item['quantity']
            if item.get('description'):
                lines.append((f"  {item['description']}", 36))
            previous_item = next((entry for entry in previous if entry.get('id') == item.get('id')), None)
            if item.get('is_custom') and previous_item and previous_item.get('takeaway') and not item.get('takeaway'):
                lines.append(('  堂食', 48))
            for modifier in visible_modifiers(item['modifiers'], previous_item['modifiers'] if previous_item else ()):
                lines.append((f"  {modifier['name']}", 48))
            if item.get('physical_bottles'):
                lines.append((f"  共 {item['physical_bottles']} 瓶", 36))
            if item.get('notes'):
                lines.append((f"备注 {item['notes']}", 36))
    lines.extend([('========================', 20), (f"{'取消' if ticket.get('order_type') == 'CANCEL' else '共'} {total} 份", 30)])
    return lines


def receipt_lines(receipt, reprint=False):
    def money(sen):
        return f'RM {sen // 100}.{sen % 100:02d}'

    lines = [('REPRINT / 重印', 25)] if reprint else []
    lines.extend([(receipt['restaurant'], 32), (receipt.get('english_name', 'KE KE / KOPITIAM'), 20),
        ('收据 / RECEIPT', 30), (f"桌号 {receipt['table']}", 40),
        (f"收据 #{receipt['receipt_number']}", 24)])
    local = datetime.fromisoformat(receipt['time']).astimezone(ZoneInfo('Asia/Kuala_Lumpur'))
    lines.append((local.strftime('%Y-%m-%d %H:%M'), 22))
    if receipt.get('cashier'):
        lines.append((f"收银 {receipt['cashier']}", 22))
    for item in receipt['items']:
        lines.extend([('------------------------', 20), (f"{item['quantity']} x {item['name']}", 40)])
        for modifier in visible_modifiers(item['modifiers']):
            lines.append((f"  {modifier['name']}", 32))
        if item.get('description'):
            lines.append((item['description'], 26))
        if item.get('physical_bottles'):
            lines.append((f"共 {item['physical_bottles']} 瓶", 26))
        if item.get('notes'):
            lines.append((f"备注 {item['notes']}", 26))
        lines.append((f"{item['quantity']} x {money(item['unit_price'])} = {money(item['line_total'])}", 24))
    method = {'CASH': '现金 CASH', 'QR': '二维码 QR', 'OTHER': '其他 OTHER'}.get(receipt['method'], receipt['method'])
    for note in receipt.get('order_notes', []):
        lines.append((f"订单 #{note['batch_id']} 备注 {note['notes']}", 26))
    if receipt.get('table_notes'):
        lines.append((f"整桌备注 {receipt['table_notes']}", 26))
    if receipt.get('original_total', receipt['total']) != receipt['total']:
        lines.extend([(f"原价 {money(receipt['original_total'])}", 28),
            (f"优惠 -{money(receipt['original_total'] - receipt['total'])}", 28)])
        if receipt.get('offer_reason'):
            lines.append((f"优惠备注 {receipt['offer_reason']}", 26))
    lines.extend([('========================', 20), (f"合计 {money(receipt['total'])}", 36),
        (method, 26), (f"实收 {money(receipt['received'])}", 28), (f"找零 {money(receipt['change'])}", 28),
        ('谢谢光临 / THANK YOU', 22)])
    return lines


def render(ticket, reprint, width, output):
    lines = ticket_lines(ticket, reprint)
    # Require an installed CJK font: silent fallback would print unreadable kitchen orders.
    fonts = {size: ImageFont.truetype(FONT_PATH, size) for size in {size for _, size in lines}}
    wrapped = []
    for text, size in lines:
        for paragraph in text.replace('\r\n', '\n').replace('\r', '\n').split('\n'):
            current = ''
            for character in paragraph:
                if fonts[size].getlength(current + character) > width - 16 and current:
                    wrapped.append((current, size))
                    current = ''
                current += character
            wrapped.append((current, size))
    height = 16 + sum(size + 12 for _, size in wrapped)
    image = Image.new('L', (width, height), 255)
    draw = ImageDraw.Draw(image)
    y = 4
    for text, size in wrapped:
        draw.text((8, y), text, font=fonts[size], fill=0)
        y += size + 12
    image = image.convert('1')
    image.save(output)
    return image
