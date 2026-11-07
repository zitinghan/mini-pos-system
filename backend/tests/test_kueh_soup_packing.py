from copy import deepcopy
import pytest
from sqlalchemy import select
from app.database.db import transaction
from app.database.seed import seed
from app.models.entities import PrintJob
from app.printing.tickets import ticket_lines
from test_v11 import catalog, selections
from test_workflows import open_session, draft, add, submit, key


@pytest.mark.parametrize('portion,egg,price',[('普通','不加蛋',800),('普通','加蛋',900),('大份','不加蛋',1000),('大份','加蛋',1100)])
def test_soup_separate_is_optional_takeaway_only_and_does_not_change_prices(client,headers,portion,egg,price):
    foods=catalog(client,headers)
    food=foods['MEE_HOON_KUEH']
    group=next(group for group in food['groups'] if group['name']=='打包设置')
    assert group['minimum']==0 and group['maximum']==1
    option=group['options'][0]
    assert option['name']=='汤分开' and option['price']==0 and not option['is_default']
    assert all(not any(section['name']=='打包设置' for section in other['groups']) for sku,other in foods.items() if sku!='MEE_HOON_KUEH')
    batch=draft(client,headers,open_session(client,headers))
    response=add(client,headers,batch,food,selections(food,'打包','汤分开',portion,egg),2)
    assert response.status_code==201 and response.json()['line_total']==price*2
    legacy=add(client,headers,batch,food,selections(food,portion,egg))
    assert legacy.status_code==201 and legacy.json()['unit_price']==price
    assert '汤分开' not in [entry['name'] for entry in legacy.json()['modifiers']]
    assert add(client,headers,batch,food,selections(food,'堂食','汤分开',portion,egg)).status_code==422
    packing_ids={entry['id'] for section in food['groups'] if section['name']=='用餐方式' for entry in section['options']}
    missing=[identity for identity in selections(food,'汤分开',portion,egg) if identity not in packing_ids]
    assert add(client,headers,batch,food,missing).status_code==422
    seed();seed()
    after=catalog(client,headers)['MEE_HOON_KUEH']
    assert len([section for section in after['groups'] if section['name']=='打包设置'])==1
    assert next(section for section in after['groups'] if section['name']=='打包设置')['options']==group['options']


def test_soup_separate_prints_and_can_be_removed_with_an_audited_correction(client,headers):
    food=catalog(client,headers)['MEE_HOON_KUEH']
    session=open_session(client,headers)
    batch=draft(client,headers,session)
    item=add(client,headers,batch,food,selections(food,'打包','汤分开')).json()
    submit(client,headers,batch)
    with transaction() as db:
        original=deepcopy(db.scalar(select(PrintJob)).ticket)
        lines=ticket_lines(original)
        assert ('【打包】',64) in lines and ('  汤分开',48) in lines
    response=client.patch(f"/api/order-batches/{batch}/items/{item['id']}",headers=key(headers),json={
        'menu_item_id':food['id'],'quantity':1,'option_ids':selections(food,'打包'),'notes':'',
        'expected_revision':1,'expected_unit_price':800})
    assert response.status_code==200 and response.json()['unit_price']==800
    with transaction() as db:
        assert db.scalar(select(PrintJob)).ticket==original
        correction=db.get(PrintJob,response.json()['change_print_job_id'])
        assert any('汤分开' in text and getattr(text,'strike',False) for text,_ in ticket_lines(correction.ticket))
    payment=client.post(f'/api/table-sessions/{session}/payments',headers=key(headers),json={
        'method':'QR','received':800,'expected_total':800}).json()
    receipt=client.get(f"/api/payments/{payment['id']}/receipt",headers=headers).json()
    assert '汤分开' not in [entry['name'] for entry in receipt['items'][0]['modifiers']]
