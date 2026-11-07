import pytest
from PIL import Image

from app.printing.tickets import render, ticket_lines


@pytest.fixture
def ticket():
    return {
        'table': 'T05',
        'batch_id': 12,
        'time': '2026-11-07T04:30:00+00:00',
        'items': [
            {
                'name': '云吞面',
                'quantity': 2,
                'modifiers': [{'name': '干捞'}, {'name': '辣'}, {'name': '加面'}],
            },
        ],
    }


@pytest.mark.parametrize('reprint', [False, True])
def test_ticket_has_current_brand_and_table_without_old_shop_names(ticket, reprint):
    lines = ticket_lines(ticket, reprint)
    text = '\n'.join(line for line, _ in lines)
    assert '可可云吞面' not in text
    assert 'KEKE WANTAN MEE' not in text
    assert lines[2 if reprint else 1][0] == '桌号 T05'
    assert '可可·南洋咖啡店' in text
    assert ('类型 REPRINT' if reprint else '类型 NEW') in text
    assert text.startswith('REPRINT / 重印') == reprint
    assert '订单 #12' in text
    assert '07/11 12:30' in text
    assert '共 2 份' in text


def test_items_and_every_selected_option_use_large_text(ticket):
    sizes = dict(ticket_lines(ticket))
    assert sizes['2 x 云吞面'] >= 48
    for option in ['干捞', '辣', '加面']:
        assert sizes[f'  {option}'] >= 48


@pytest.mark.parametrize('width', [192, 384, 576])
def test_large_long_items_and_options_wrap_inside_printable_width(ticket, tmp_path, width):
    original = render(ticket, False, width, tmp_path / 'original.png')
    ticket['items'][0]['name'] = '云吞面' * 8
    ticket['items'][0]['modifiers'].append({'name': '加面加辣不要葱' * 5})
    output = tmp_path / 'long-ticket.png'
    image = render(ticket, False, width, output)
    assert image.mode == '1'
    assert image.width == width
    assert image.height > original.height
    ink = image.convert('L').point(lambda pixel: 255 - pixel).getbbox()
    assert ink is not None
    assert ink[0] >= 8
    assert ink[2] <= width - 8
    assert ink[3] < image.height
    with Image.open(output) as saved:
        assert saved.size == image.size
        assert saved.mode == '1'
