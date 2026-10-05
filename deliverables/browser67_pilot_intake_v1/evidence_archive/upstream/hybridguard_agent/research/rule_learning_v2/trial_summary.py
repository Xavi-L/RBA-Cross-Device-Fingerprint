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
    prediction_file = 'failure_predictions.jsonl' if worker_failed else 'predictions.jsonl'
    predictions = safely(prediction_file, lines)
    expected = job['outer_test_ids']
    if predictions is not None:
        try:
            if [r['opaque_id'] for r in predictions] != expected:
                raise ValueError('EXPECTED_MEMBER_ORDER_OR_CLOSURE_MISMATCH')
            for r in predictions:
                if not isinstance(r, dict):
                    raise ValueError('PREDICTION_EXPECTED_OBJECT')
                if r['decision'] not in DECISIONS:
                    raise ValueError('INVALID_DECISION')
                for n, d in [('selected_atoms_available', 'selected_atoms_expected'),
                             ('clauses_defined', 'clauses_expected')]:
                    if r[d] is not None and not (type(r[d]) is int and type(r[n]) is int and 0 <= r[n] <= r[d]):
                        raise ValueError('INVALID_CELL_COUNTS')
                    if r[d] is None and r[n] is not None:
                        raise ValueError('INCONSISTENT_UNKNOWN_CELL_COUNTS')
        except (ValueError, KeyError, TypeError) as exc:
            issues.append({'artifact': prediction_file, 'reason': str(exc)})
            predictions = None
    model = safely('model.json', model_loader)
    training = safely('training.json', read)
    if not isinstance(training, dict):
        issues.append({'artifact': 'training.json', 'reason': 'EXPECTED_OBJECT'})
        training = None
    if not isinstance(receipt, dict):
        issues.append({'artifact': 'receipt.json', 'reason': 'EXPECTED_OBJECT'})
    # Shape validation is unconditional: valid JSON null is not a valid object.
    # A worker failure marker still dominates all partially written artifacts.
    if not worker_failed:
        if isinstance(receipt, dict):
            if receipt.get('state') not in ('FITTED', 'EMPTY_MODEL', 'FAILED') or not isinstance(receipt.get('model_id'), str) or not receipt['model_id']:
                issues.append({'artifact': 'receipt.json', 'reason': 'REQUIRED_STATE_OR_MODEL_ID'})
            if 'predictions' in receipt and (type(receipt['predictions']) is not int or receipt['predictions'] != len(expected)):
                issues.append({'artifact': 'receipt.json', 'reason': 'PREDICTION_COUNT_MISMATCH'})
        if model is None:
            issues.append({'artifact': 'model.json', 'reason': 'REQUIRED_MODEL_UNAVAILABLE'})
        else:
            try:
                if model.status not in ('FITTED', 'EMPTY_MODEL', 'FAILED'):
                    raise ValueError('MODEL_STATUS_INVALID')
                if (model.status == 'FITTED') != bool(model.clauses):
                    raise ValueError('MODEL_STATUS_STRUCTURE_MISMATCH')
                if not isinstance(model.fit, dict) or not isinstance(model.fit.get('train_ids'), list) or not all(isinstance(i, str) for i in model.fit['train_ids']):
                    raise ValueError('MODEL_REQUIRED_TRAIN_MEMBERS')
                if model.binding.get('fold_id') != job['fold_id']:
                    raise ValueError('MODEL_FOLD_BINDING_MISMATCH')
                if 'train_ids' in job and model.fit['train_ids'] != job['train_ids']:
                    raise ValueError('MODEL_TRAIN_BINDING_MISMATCH')
                for key in ('method', 'representation'):
                    actual = model.method_id if key == 'method' else model.view.get('representation')
                    if key in job and actual != job[key]:
                        raise ValueError('MODEL_JOB_BINDING_MISMATCH:' + key)
                if isinstance(receipt, dict) and (receipt.get('model_id') != model.model_id or receipt.get('state') != model.status):
                    issues.append({'artifact': 'receipt.json', 'reason': 'RECEIPT_MODEL_BINDING_MISMATCH'})
            except (ValueError, KeyError, TypeError, AttributeError) as exc:
                issues.append({'artifact': 'model.json', 'reason': str(exc)})
        if training is not None:
            try:
                for key in ('trace', 'candidate_manifest', 'atoms', 'access_operations'):
                    if not isinstance(training.get(key), list) or not all(isinstance(x, dict) for x in training[key]):
                        raise ValueError('REQUIRED_LIST_OF_OBJECTS:' + key)
                candidates = training['candidate_manifest']
                if any(not isinstance(c.get('clause_id'), str) or type(c.get('eligible')) is not bool for c in candidates):
                    raise ValueError('CANDIDATE_REQUIRED_ID_AND_ELIGIBILITY')
                if len({c['clause_id'] for c in candidates}) != len(candidates):
                    raise ValueError('DUPLICATE_CANDIDATE_ID')
                if any(not isinstance(a.get('atom_id'), str) for a in training['atoms']):
                    raise ValueError('ATOM_REQUIRED_ID')
                if model is not None:
                    selected = {c.id for c in model.clauses}
                    if not selected <= {c['clause_id'] for c in candidates if c['eligible']}:
                        raise ValueError('SELECTED_CLAUSE_TRAIN_BINDING_MISMATCH')
                    if any('selected' in c and (type(c['selected']) is not bool or c['selected'] != (c['clause_id'] in selected)) for c in candidates):
                        raise ValueError('TRAINING_SELECTED_FLAGS_MISMATCH')
                    if not {a.atom_id for a in model.atoms} <= {a['atom_id'] for a in training['atoms']}:
                        raise ValueError('TRAINING_ATOM_BINDING_MISMATCH')
                    if 'train_ids_once' in training and training['train_ids_once'] != model.fit['train_ids']:
                        raise ValueError('TRAINING_MEMBER_BINDING_MISMATCH')
                    if any(op.get('ids') != model.fit['train_ids'] for op in training['access_operations']):
                        raise ValueError('TRAINING_ACCESS_MEMBER_BINDING_MISMATCH')
            except (ValueError, KeyError, TypeError, AttributeError) as exc:
                issues.append({'artifact': 'training.json', 'reason': str(exc)})
        if predictions is not None and model is not None:
            try:
                for r in predictions:
                    if r.get('model_id') != model.model_id or r.get('model_status') != model.status or r.get('method_id') != model.method_id:
                        raise ValueError('PREDICTION_MODEL_BINDING_MISMATCH')
                    if any(r.get(k) != v for k, v in model.binding.items()):
                        raise ValueError('PREDICTION_CONTEXT_BINDING_MISMATCH')
                    if not isinstance(r.get('atom_explanations'), list) or not isinstance(r.get('clause_explanations'), list):
                        raise ValueError('PREDICTION_REQUIRED_EXPLANATIONS')
                    mapping = {'MANIPULATION_ALERT':'T', 'NO_ALERT':'F', 'INSUFFICIENT_EVIDENCE':'U'}
                    if r['decision'] in mapping and r.get('logical_state') != mapping[r['decision']]:
                        raise ValueError('DECISION_LOGIC_MISMATCH')
                    if model.status != 'FITTED' and r['decision'] != model.status:
                        raise ValueError('MODEL_STATE_DECISION_MISMATCH')
                    if model.status == 'FITTED' and r['decision'] == 'EMPTY_MODEL':
                        raise ValueError('FITTED_MODEL_CANNOT_BE_EMPTY')
            except (ValueError, KeyError, TypeError) as exc:
                issues.append({'artifact': prediction_file, 'reason': str(exc)})
    status = ('WORKER_FAILED' if worker_failed else 'INTEGRITY_EXCEPTION' if issues else
              'MODEL_FAILED' if model.status == 'FAILED' else 'OK')
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
