from datetime import datetime
from zoneinfo import ZoneInfo
from PIL import Image, ImageDraw, ImageFont
from app.core.config import FONT_PATH


def ticket_lines(ticket, reprint=False):
    lines = []
    if reprint:
        lines.append(('REPRINT / 重印', 25))
    lines.extend([('可可云吞面', 30), ('KEKE WANTAN MEE', 18), (f"桌号 {ticket['table']}", 48)])
    lines.append((f"订单 #{ticket.get('batch_id', 'TEST')}", 22))
    timestamp = datetime.fromisoformat(ticket['time']).astimezone(ZoneInfo('Asia/Kuala_Lumpur'))
    lines.append((timestamp.strftime('%d/%m %H:%M'), 20))
    total = 0
    for item in ticket['items']:
        lines.append(('------------------------', 20))
        lines.append((f"{item['quantity']} x {item['name']}", 30))
        total += item['quantity']
        for modifier in item['modifiers']:
            lines.append((f"  {modifier['name']}", 25))
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
