def job_data(job):
    return {**{key: getattr(job, key) for key in (
        'id', 'batch_id', 'payment_id', 'change_id', 'printer_mode', 'routing_group', 'status', 'attempts',
        'reprint', 'error', 'preview', 'created_at', 'updated_at')},
        'document_type': job.ticket.get('kind', 'KITCHEN'),
        'table': job.ticket.get('table'), 'order_type': job.ticket.get('order_type', 'NEW'),
        'notes': job.ticket.get('notes', '')}
