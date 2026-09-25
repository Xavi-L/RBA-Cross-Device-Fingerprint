"""Read-only trial reconciliation; damaged evidence never aborts the denominator."""
from pathlib import Path

from hybridguard_agent.research.rule_learning.contracts import DECISIONS
from .adapter import load_model
from .common import read, lines
from .pilot import failed_rows


def inspect_attempt(directory, job, model_loader=load_model):
    """Return derived decisions and optional trusted structure; never rewrite a trial.

    A failed worker dominates partial outputs. A formerly successful but now
    unreadable/inconsistent artifact is an INTEGRITY_EXCEPTION, not an empty
    model. Its saved receipt/predictions remain evidence; this readback uses
    FAILED rows for every expected member until the anomaly is resolved.
    """
    directory = Path(directory)
    issues = []

    def safely(name, reader):
        try:
            return reader(directory / name)
        except Exception as exc:
            issues.append({'artifact': name, 'reason': type(exc).__name__ + ': ' + str(exc)})
            return None

    worker_failed = (directory / 'worker_failure.json').exists()
    receipt = safely('worker_failure.json' if worker_failed else 'receipt.json', read)
    failed = worker_failed or isinstance(receipt, dict) and receipt.get('state') == 'FAILED'
    prediction_file = 'failure_predictions.jsonl' if worker_failed else 'predictions.jsonl'
    predictions = safely(prediction_file, lines)
    expected = job['outer_test_ids']
    if predictions is not None:
        try:
            if [r['opaque_id'] for r in predictions] != expected:
                raise ValueError('EXPECTED_MEMBER_ORDER_OR_CLOSURE_MISMATCH')
            for r in predictions:
                if r['decision'] not in DECISIONS:
                    raise ValueError('INVALID_DECISION')
                for n, d in [('selected_atoms_available', 'selected_atoms_expected'),
                             ('clauses_defined', 'clauses_expected')]:
                    if r[d] is not None and not (type(r[d]) is int and type(r[n]) is int and 0 <= r[n] <= r[d]):
                        raise ValueError('INVALID_CELL_COUNTS')
        except (ValueError, KeyError, TypeError) as exc:
            issues.append({'artifact': prediction_file, 'reason': str(exc)})
            predictions = None
    model = safely('model.json', model_loader)
    training = safely('training.json', read)
    if training is not None and not isinstance(training, dict):
        issues.append({'artifact': 'training.json', 'reason': 'EXPECTED_OBJECT'})
        training = None
    if not failed and isinstance(receipt, dict) and model is not None:
        if receipt.get('model_id') != model.model_id or receipt.get('state') != model.status:
            issues.append({'artifact': 'receipt.json', 'reason': 'RECEIPT_MODEL_BINDING_MISMATCH'})
        if predictions is not None and any(r.get('model_id') != model.model_id for r in predictions):
            issues.append({'artifact': prediction_file, 'reason': 'PREDICTION_MODEL_BINDING_MISMATCH'})
    if receipt is not None and not isinstance(receipt, dict):
        issues.append({'artifact': 'receipt.json', 'reason': 'EXPECTED_OBJECT'})
    status = 'WORKER_FAILED' if failed else 'INTEGRITY_EXCEPTION' if issues else 'OK'
    if status != 'OK':
        # Reconstruct in memory even if a failed prediction file is incomplete.
        # Partial predictions, damaged JSON and original receipts stay untouched.
        predictions = failed_rows(job, status)
    return {'predictions': predictions, 'model': model if status == 'OK' else None,
            'training': training if status == 'OK' else None,
            'audit': {'status': status, 'expected_n': len(expected), 'issues': issues,
                      'receipt_state': receipt.get('state') if isinstance(receipt, dict) else None,
                      'model_readable': model is not None, 'training_readable': training is not None,
                      'structure_statistics': 'AVAILABLE' if status == 'OK' else 'NOT_AVAILABLE_UNTRUSTED_OR_FAILED_ATTEMPT',
                      'prediction_evidence': prediction_file, 'trial_files_modified': False}}
