from copy import deepcopy
from sqlalchemy import select
from app.database.db import transaction
from app.database.seed import seed
from app.models.entities import MenuItem,ModifierOption,PrintJob
from app.printing.tickets import ticket_lines
from test_v11 import catalog,selections
from test_workflows import open_session,draft,add,submit,key


def test_existing_wantan_adds_less_spicy_once_without_changing_configured_defaults(client,headers):
    food=catalog(client,headers)['WANTAN_MEE']
    group=next(group for group in food['groups'] if group['name']=='辣度')
    original_ids={option['name']:option['id'] for option in group['options'] if option['name']!='少辣'}
    with transaction() as db:
        db.delete(db.get(ModifierOption,next(option['id'] for option in group['options'] if option['name']=='少辣')))
        for option in group['options']:
            if option['name']!='少辣':db.get(ModifierOption,option['id']).is_default=option['name']=='辣'
        item=db.get(MenuItem,food['id']);item.base_price=850;item.sold_out=True
    seed();seed()
    after=catalog(client,headers)['WANTAN_MEE']
    assert after['base_price']==850 and after['sold_out']
    spicy=next(section for section in after['groups'] if section['name']=='辣度')
    assert spicy['minimum']==spicy['maximum']==1 and len(spicy['options'])==3
    for option in spicy['options']:
        assert option['is_default']==(option['name']=='辣')
        if option['name']=='少辣':assert option['price']==0
        else:assert option['id']==original_ids[option['name']]


def test_less_spicy_prints_and_can_replace_spicy_without_repricing_or_rewriting_old_tickets(client,headers):
    food=catalog(client,headers)['WANTAN_MEE']
    session=open_session(client,headers);batch=draft(client,headers,session)
    item=add(client,headers,batch,food,selections(food,'辣')).json()
    assert submit(client,headers,batch).status_code==200
    with transaction() as db:original=deepcopy(db.scalar(select(PrintJob)).ticket)
    both=selections(food,'辣')+[option['id'] for group in food['groups'] for option in group['options'] if option['name']=='少辣']
    assert add(client,headers,draft(client,headers,session),food,both).status_code==422
    response=client.patch(f"/api/order-batches/{batch}/items/{item['id']}",headers=key(headers),json={
        'menu_item_id':food['id'],'quantity':1,'option_ids':selections(food,'少辣'),'expected_revision':1,'expected_unit_price':800})
    assert response.status_code==200 and response.json()['unit_price']==800
    with transaction() as db:
        assert db.scalar(select(PrintJob)).ticket==original
        correction=db.get(PrintJob,response.json()['change_print_job_id'])
        lines=ticket_lines(correction.ticket)
        assert any(text.strip()=='辣' and getattr(text,'strike',False) for text,_ in lines)
        assert any(text.strip()=='少辣' and not getattr(text,'strike',False) for text,_ in lines)
    paid=client.post(f'/api/table-sessions/{session}/payments',headers=key(headers),json={
        'method':'QR','expected_total':800,'received':800,'discard_drafts':True})
    assert paid.status_code==200
    receipt=client.get(f"/api/payments/{paid.json()['id']}/receipt",headers=headers).json()
    assert '少辣' in [option['name'] for option in receipt['items'][0]['modifiers']]
