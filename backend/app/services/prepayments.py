"""Manual money already collected, finalized exactly once at cashier settlement."""
import hashlib
import json


def summary(batches, items):
    rounds = []
    for batch in batches:
        if batch.status != 'SUBMITTED' or not batch.prepaid_label:
            continue
        rows = [item for item in items if item.batch_id == batch.id]
        estimated = batch.prepaid_amount is None
        amount = batch.prepaid_amount if not estimated else sum(item.line_total for item in rows if item.status == 'SUBMITTED')
        rounds.append({'batch_id': batch.id, 'method': batch.prepaid_method, 'amount': amount,
            'amount_estimated': estimated, 'info_revision': batch.info_revision})
    token = hashlib.sha256(json.dumps(rounds, sort_keys=True).encode()).hexdigest()
    return {'rounds': rounds, 'total': sum(row['amount'] for row in rounds), 'token': token}


def allocate(rounds, additional_method, remaining):
    amounts = {'CASH': 0, 'QR': 0, 'OTHER': 0}
    for row in rounds:
        amounts[row['method'] or 'OTHER'] += row['amount']
    if remaining:
        amounts[additional_method] += remaining
    return {method: amount for method, amount in amounts.items() if amount > 0}
