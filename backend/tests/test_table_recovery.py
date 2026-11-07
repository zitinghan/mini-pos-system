from copy import deepcopy
import pytest
from sqlalchemy import select, func, inspect
from app.database.db import transaction
from app.models.entities import TableSession, OrderBatch, OrderItem, Payment, PaymentReversal, Receipt, PrintJob, AuditLog
from app.services import table_controls
from app.printing.tickets import ticket_lines
from test_table_controls import placed
from test_v11 import catalog, selections
from test_workflows import open_session, draft, add, submit, key


def preview(client, headers, session):
    return next(row for row in client.get('/api/table-recovery',headers=headers).json() if row['session_id']==session)

def restore(client, headers, session, value=None, request=None):
    item=value or preview(client,headers,session)
    return client.post(f'/api/table-sessions/{session}/restore',headers=request or key(headers),
        json={'expected_change_token':item['expected_change_token'],'reason':'误关桌台'})

def cancel(client, headers, session):
    bill=client.get(f'/api/table-sessions/{session}/bill',headers=headers).json()
    result=client.post(f'/api/table-sessions/{session}/cancel',headers=key(headers),json={'expected_change_token':bill['change_token']})
    assert result.status_code==200

def row_snapshot(row):
    return {column.key:getattr(row,column.key) for column in inspect(row).mapper.column_attrs}


def test_cancelled_table_restores_only_preclosure_items_drafts_and_original_stalls(client, headers):
    session,batch,before=placed(client,headers,('WANTAN_MEE','CURRY_RICE','MILO'),prepaid=True)
    line=before['items'][-1]
    client.post(f"/api/order-batches/{batch}/items/{line['id']}/cancel",headers=key(headers),json={'expected_revision':1})
    token=client.post('/api/auth/login',json={'name':'staff','pin':'654321'}).json()['token']
    staff={'Authorization':f'Bearer {token}'}
    unfinished=draft(client,staff,session)
    add(client,staff,unfinished,catalog(client,staff)['PLAIN_WATER'])
    current=client.get(f'/api/table-sessions/{session}/bill',headers=headers).json()
    cancel(client,headers,session)
    with transaction() as db: old_jobs=deepcopy([job.ticket for job in db.scalars(select(PrintJob).order_by(PrintJob.id))])
    item=preview(client,headers,session)
    assert item['total']==1600 and len(item['items'])==3
    request=key(headers)
    response=restore(client,headers,session,item,request)
    assert response.status_code==200,response.text
    assert restore(client,headers,session,item,request).json()==response.json()
    assert restore(client,headers,session,item).status_code==409
    bill=client.get(f'/api/table-sessions/{session}/bill',headers=headers).json()
    assert bill['total']==1600 and bill['first_order_at']==current['first_order_at'] and bill['paid_at'] is None
    assert client.get('/api/tables/5',headers=headers).json()['prepaid_label_status']=='ALL'
    with transaction() as db:
        assert db.get(OrderBatch,unfinished).status=='DRAFT'
        assert db.get(OrderItem,line['id']).status=='CANCELLED'
        assert db.get(TableSession,session).closed_at is None
        jobs=list(db.scalars(select(PrintJob).order_by(PrintJob.id)))
        assert [job.ticket for job in jobs[:len(old_jobs)]]==old_jobs
        recovery=[job for job in jobs if job.ticket.get('order_type')=='RESTORE']
        assert {job.routing_group for job in recovery}=={'KITCHEN','RICE'}
        assert sum(len(job.ticket['items']) for job in recovery)==2
        assert all('已制作请勿重复出餐' in '\n'.join(line for line,_ in ticket_lines(job.ticket)) for job in recovery)
        assert db.scalar(select(func.count()).select_from(Payment))==0


def test_paid_restore_reverses_revenue_keeps_originals_and_reuses_frozen_prices(client, headers):
    session,batch,_=placed(client,headers,('WANTAN_MEE','CURRY_RICE','MILO'),prepaid=True)
    result=client.patch(f'/api/order-batches/{batch}/details',headers=key(headers),json={
        'prepaid_label':True,'prepaid_method':'QR','prepaid_amount':1850,'notes':'','expected_revision':1})
    assert result.status_code==200
    credit=client.get(f'/api/table-sessions/{session}/bill',headers=headers).json()
    request=key(headers)
    body={'expected_total':1900,'received':0,'final_total':1850,'offer_reason':'熟客优惠',
        'expected_prepaid_total':1850,'expected_prepaid_token':credit['prepaid_token']}
    payment=client.post(f'/api/table-sessions/{session}/payments',headers=request,json=body).json()
    with transaction() as db:
        original_payment=row_snapshot(db.get(Payment,payment['id']))
        original_session=row_snapshot(db.get(TableSession,session))
        original_receipt=deepcopy(db.scalar(select(Receipt)).snapshot)
        old_job_count=db.scalar(select(func.count()).select_from(PrintJob))
    food=catalog(client,headers)['WANTAN_MEE']
    client.patch(f"/api/menu/items/{food['id']}",headers=headers,json={'price':1200})
    reviewed=preview(client,headers,session)
    recovery_request=key(headers)
    response=restore(client,headers,session,reviewed,recovery_request)
    assert response.status_code==200,response.text
    result=response.json(); recovered=result['session_id']
    assert recovered!=session and result['voided_amount']==1850 and result['print_jobs']==[]
    assert restore(client,headers,session,reviewed,recovery_request).json()==result
    assert restore(client,headers,session,reviewed).status_code==409
    assert client.post(f'/api/table-sessions/{session}/payments',headers=request,json=body).status_code==409
    bill=client.get(f'/api/table-sessions/{recovered}/bill',headers=headers).json()
    assert bill['total']==1900 and not bill['has_prepaid_label']
    assert bill['recovery_offer']=={'original_total':1900,'total':1850,'offer_reason':'熟客优惠'}
    assert bill['first_order_at']==original_session['first_order_at'] and bill['paid_at'] is None
    report=client.get('/api/reports/daily-sales',headers=headers).json()
    assert report['total']==report['completed_sessions']==0 and sum(report['category_sales'].values())==0
    history=client.get('/api/reports/transactions',headers=headers).json()
    assert len(history)==1 and history[0]['voided'] and history[0]['restored_session_id']==recovered
    receipt=client.get(f"/api/payments/{payment['id']}/receipt",headers=headers).json()
    assert receipt['voided'] and receipt['items']==original_receipt['items']
    assert client.post(f"/api/payments/{payment['id']}/receipt/print",headers=key(headers)).status_code==409
    with transaction() as db:
        assert row_snapshot(db.get(Payment,payment['id']))==original_payment
        assert row_snapshot(db.get(TableSession,session))==original_session
        assert db.scalar(select(Receipt)).snapshot==original_receipt
        assert db.scalar(select(func.count()).select_from(PrintJob))==old_job_count
        assert db.scalar(select(func.count()).select_from(PaymentReversal))==1
    second=client.post(f'/api/table-sessions/{recovered}/payments',headers=key(headers),json={
        'method':'QR','expected_total':1900,'received':1850,'final_total':1850,'offer_reason':'熟客优惠'})
    assert second.status_code==200
    report=client.get('/api/reports/daily-sales',headers=headers).json()
    assert report['total']==1850 and report['completed_sessions']==1
    assert sum(report['category_sales'].values())==1850
    assert len(client.get('/api/reports/transactions',headers=headers).json())==2


def test_restore_does_not_overwrite_a_new_customer_and_only_retires_empty_shells(client,headers):
    session,_,_=placed(client,headers)
    cancel(client,headers,session)
    shell=open_session(client,headers)
    assert shell!=session
    assert restore(client,headers,session).status_code==200
    with transaction() as db: assert db.get(TableSession,shell).status=='CANCELLED'
    cancel(client,headers,session)
    replacement=open_session(client,headers)
    batch=draft(client,headers,replacement)
    add(client,headers,batch,catalog(client,headers)['PLAIN_WATER'])
    assert not preview(client,headers,session)['can_restore']
    assert restore(client,headers,session).status_code==409
    with transaction() as db: assert db.get(TableSession,replacement).status=='OCCUPIED'


def test_restore_is_admin_only_and_outbox_failure_rolls_back(client,headers,monkeypatch):
    session,_,_=placed(client,headers)
    cancel(client,headers,session)
    item=preview(client,headers,session)
    token=client.post('/api/auth/login',json={'name':'staff','pin':'654321'}).json()['token']
    staff={'Authorization':f'Bearer {token}'}
    assert client.get('/api/table-recovery',headers=staff).status_code==403
    assert restore(client,staff,session,item).status_code==403
    bad={**item,'expected_change_token':'0'*64}
    assert restore(client,headers,session,bad).status_code==409
    def fail(**kwargs): raise RuntimeError('Restore notice failed')
    monkeypatch.setattr(table_controls,'PrintJob',fail)
    with pytest.raises(RuntimeError,match='Restore notice failed'): restore(client,headers,session,item)
    with transaction() as db:
        assert db.get(TableSession,session).status=='CANCELLED'
        assert not db.scalar(select(AuditLog).where(AuditLog.action=='RESTORE_TABLE'))


def test_paid_receipt_sending_blocks_restore_then_pending_receipt_is_stopped(client,headers):
    session,_,_=placed(client,headers)
    payment=client.post(f'/api/table-sessions/{session}/payments',headers=key(headers),
        json={'method':'QR','expected_total':800,'received':800,'print_receipt':True}).json()
    with transaction() as db:
        job=db.scalar(select(PrintJob).where(PrintJob.payment_id==payment['id']))
        job.status='SENDING'; job_id=job.id
    assert not preview(client,headers,session)['can_restore']
    assert restore(client,headers,session).status_code==409
    with transaction() as db: db.get(PrintJob,job_id).status='PENDING'
    assert restore(client,headers,session).status_code==200
    with transaction() as db:
        assert db.get(PrintJob,job_id).status=='FAILED'
        assert '收款已撤销' in db.get(PrintJob,job_id).error
    assert client.post(f'/api/print-jobs/{job_id}/retry',headers=key(headers)).status_code==409


def test_closed_empty_draft_restores_without_sending_unsubmitted_food(client,headers):
    session=open_session(client,headers)
    batch=draft(client,headers,session)
    add(client,headers,batch,catalog(client,headers)['WANTAN_MEE'])
    client.post(f'/api/table-sessions/{session}/close-empty',headers=headers)
    response=restore(client,headers,session)
    assert response.status_code==200 and response.json()['print_jobs']==[]
    with transaction() as db:
        assert db.get(OrderBatch,batch).status=='DRAFT'
        assert db.scalar(select(OrderItem)).status=='DRAFT'
    assert client.get('/api/tables/5',headers=headers).json()['status']=='AVAILABLE'


def test_takeaway_waiting_and_paid_table_notes_follow_active_items_and_rounds(client,headers):
    food=catalog(client,headers)['WANTAN_MEE']
    session=open_session(client,headers)
    batch=draft(client,headers,session)
    add(client,headers,batch,food,selections(food,'打包'))
    client.post(f'/api/order-batches/{batch}/submit',headers=key(headers),json={'prepaid_label':True})
    table=client.get('/api/tables/5',headers=headers).json()
    assert table['all_takeaway'] and table['prepaid_label_status']=='ALL'
    extra=draft(client,headers,session)
    add(client,headers,extra,food)
    submit(client,headers,extra)
    table=client.get('/api/tables/5',headers=headers).json()
    assert not table['all_takeaway'] and table['prepaid_label_status']=='PARTIAL'
