from copy import deepcopy
import pytest
from sqlalchemy import select, func
from app.database.db import transaction
from app.models.entities import OrderBatch, Payment, PrintJob, AuditLog
from app.printing.tickets import ticket_lines
from test_v11 import catalog
from test_workflows import open_session, draft, add, submit, key


@pytest.mark.parametrize('method',['CASH','QR','OTHER'])
def test_paid_first_method_is_snapshotted_printed_editable_and_not_a_payment(client,headers,method):
    session=open_session(client,headers)
    batch=draft(client,headers,session)
    add(client,headers,batch,catalog(client,headers)['WANTAN_MEE'])
    request=key(headers)
    payload={'prepaid_label':True,'prepaid_method':method}
    endpoint=f'/api/order-batches/{batch}/submit'
    submitted=client.post(endpoint,headers=request,json=payload)
    assert submitted.status_code==200
    original=client.get(f'/api/table-sessions/{session}/orders',headers=headers).json()[0]
    assert original['prepaid_method']==method and original['prepaid_label']
    bill=client.get(f'/api/table-sessions/{session}/bill',headers=headers).json()
    assert bill['prepaid_rounds']==[{'batch_id':batch,'method':method}]
    with transaction() as db:
        job=db.scalar(select(PrintJob)); old_ticket=deepcopy(job.ticket)
        assert old_ticket['prepaid_method']==method
        assert method in '\n'.join(line for line,_ in ticket_lines(old_ticket))
        assert db.scalar(select(func.count()).select_from(Payment))==0
    replacement='OTHER' if method!='OTHER' else 'CASH'
    details={'prepaid_label':True,'prepaid_method':replacement,'expected_revision':1,'notes':'已经收钱'}
    change_request=key(headers)
    changed=client.patch(f'/api/order-batches/{batch}/details',headers=change_request,json=details)
    assert changed.status_code==200 and changed.json()['prepaid_method']==replacement
    assert client.patch(f'/api/order-batches/{batch}/details',headers=change_request,json=details).json()==changed.json()
    assert client.patch(f'/api/order-batches/{batch}/details',headers=key(headers),json=details).status_code==409
    assert client.post(endpoint,headers=request,json=payload).status_code==200
    assert client.post(endpoint,headers=request,json={**payload,'prepaid_method':replacement}).status_code==409
    with transaction() as db:
        jobs=list(db.scalars(select(PrintJob).order_by(PrintJob.id)))
        assert len(jobs)==2 and jobs[0].ticket==old_ticket
        assert jobs[1].ticket['order_type']=='NOTE' and jobs[1].ticket['items']==[]
        assert jobs[1].ticket['prepaid_method']==replacement
        assert '请勿重复制作' in '\n'.join(line for line,_ in ticket_lines(jobs[1].ticket))
        audit=db.scalar(select(AuditLog).where(AuditLog.action=='BATCH_DETAILS'))
        assert audit.details['before']['prepaid_method']==method and audit.details['after']['prepaid_method']==replacement
        assert db.scalar(select(func.count()).select_from(Payment))==0
    extra=draft(client,headers,session)
    add(client,headers,extra,catalog(client,headers)['MILO'])
    submit(client,headers,extra)
    with transaction() as db:
        assert not db.get(OrderBatch,extra).prepaid_label and db.get(OrderBatch,extra).prepaid_method is None
    assert client.get('/api/tables/5',headers=headers).json()['prepaid_label_status']=='PARTIAL'


def test_legacy_unknown_methods_are_preserved_notes_edits_do_not_clear_known_methods_and_unmark_clears(client,headers):
    session=open_session(client,headers)
    batch=draft(client,headers,session)
    add(client,headers,batch,catalog(client,headers)['MILO'])
    client.post(f'/api/order-batches/{batch}/submit',headers=key(headers),json={'prepaid_label':True})
    endpoint=f'/api/order-batches/{batch}/details'
    with transaction() as db: assert db.get(OrderBatch,batch).prepaid_method is None
    result=client.patch(endpoint,headers=key(headers),json={'prepaid_label':True,'prepaid_method':'CASH','notes':'','expected_revision':1})
    assert result.json()['prepaid_method']=='CASH'
    legacy=client.patch(endpoint,headers=key(headers),json={'prepaid_label':True,'notes':'改备注','expected_revision':2})
    assert legacy.status_code==200 and legacy.json()['prepaid_method']=='CASH'
    cleared=client.patch(endpoint,headers=key(headers),json={'prepaid_label':False,'prepaid_method':'CASH','notes':'改备注','expected_revision':3})
    assert cleared.status_code==200 and cleared.json()['prepaid_method'] is None
    assert client.patch(endpoint,headers=key(headers),json={'prepaid_label':True,'prepaid_method':'BANK','notes':'','expected_revision':4}).status_code==422
    payment=client.post(f'/api/table-sessions/{session}/payments',headers=key(headers),json={'method':'QR','expected_total':300,'received':300})
    assert payment.status_code==200
    assert client.patch(endpoint,headers=key(headers),json={'prepaid_label':True,'prepaid_method':'QR','notes':'','expected_revision':4}).status_code==409
