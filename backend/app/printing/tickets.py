from datetime import datetime
from zoneinfo import ZoneInfo
from PIL import Image, ImageDraw, ImageFont
from app.core.config import FONT_PATH


def ticket_lines(ticket, reprint=False):
    lines = []
    if reprint:
        lines.append(('REPRINT / 重印', 25))
    lines.append((ticket.get('restaurant', '可可·南洋咖啡店'), 32))
    lines.append((f"桌号 {ticket['table']}", 48))
    number = ticket.get('ticket_number', ticket.get('batch_id', 'TEST'))
    lines.append((f"票号 #{str(number).zfill(6)}", 22))
    lines.append((f"订单 #{ticket.get('batch_id', 'TEST')}", 22))
    order_type = 'REPRINT' if reprint else ticket.get('order_type', 'NEW')
    lines.append((f"类型 {order_type}", 25))
    timestamp = datetime.fromisoformat(ticket['time']).astimezone(ZoneInfo('Asia/Kuala_Lumpur'))
    lines.append((timestamp.strftime('%d/%m %H:%M'), 20))
    total = 0
    for station, label in [('KITCHEN', '厨房'), ('BEVERAGE', '饮料')]:
        items = [item for item in ticket['items'] if item.get('printer_group', 'KITCHEN') == station]
        if not items:
            continue
        lines.append((f'----- {label} -----', 30))
        for item in items:
            lines.append(('------------------------', 20))
            lines.append((f"{item['quantity']} x {item['name']}", 48))
            total += item['quantity']
            if item.get('description'):
                lines.append((f"  {item['description']}", 36))
            for modifier in item['modifiers']:
                lines.append((f"  {modifier['name']}", 48))
            if item.get('physical_bottles'):
                lines.append((f"  共 {item['physical_bottles']} 瓶", 36))
            if item.get('notes'):
                lines.append((f"备注 {item['notes']}", 36))
    lines.extend([('========================', 20), (f'共 {total} 份', 30)])
    return lines


def render(ticket, reprint, width, output):
    lines = ticket_lines(ticket, reprint)
    # Require an installed CJK font: silent fallback would print unreadable kitchen orders.
    fonts = {size: ImageFont.truetype(FONT_PATH, size) for size in {size for _, size in lines}}
    wrapped = []
    for text, size in lines:
        current = ''
        for character in text:
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
