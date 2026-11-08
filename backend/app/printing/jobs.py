def job_data(job):
    return {**{key: getattr(job, key) for key in (
        'id', 'batch_id', 'session_id', 'payment_id', 'change_id', 'printer_mode', 'routing_group', 'status', 'attempts',
        'reprint', 'error', 'preview', 'created_at', 'updated_at')},
        'document_type': job.ticket.get('kind', 'KITCHEN'),
        'order_number': job.ticket.get('order_number', job.batch_id),
        'table': job.ticket.get('table'), 'order_type': job.ticket.get('order_type', 'NEW'),
        'notes': job.ticket.get('notes', ''), 'table_notes': job.ticket.get('table_notes', ''),
        'prepaid_label': job.ticket.get('prepaid_label', False), 'prepaid_method': job.ticket.get('prepaid_method'), 'reason': job.ticket.get('reason', '')}
