"""Opt-in current-App relation cells alongside the unchanged legacy WEBGL50."""
from copy import deepcopy
from dataclasses import asdict

from . import mtc_reselection_candidates as old
from . import mtc_screen_relations as screen
from . import mtc_resource_relations as resource
from .rule_learning.contracts import cell
from .rule_learning_v2.semantic_selection import semantic_catalog

VERSION = 'mtc-relation-candidate-adapter-v1'


def registered_atoms():
    atoms = tuple(screen.registered_atoms()) + tuple(resource.registered_atoms())
    if not 1 <= len(atoms) <= 4 or len(screen.registered_atoms()) > 2 or len(resource.registered_atoms()) > 2:
        raise ValueError('RELATION_TEMPLATE_SCOPE_EXCEEDED')
    for atom in atoms:
        refs = atom.provenance['field_refs']
        expected = set()
        for field in refs:
            if field.startswith('app.android_native_data.'):
                expected.add('native84')
            elif field.startswith('app.webview_data.'):
                expected.add('host26')
            elif field.startswith('app.web_data.'):
                expected.add('app_web67')
            else:
                raise ValueError('ONLY_CURRENT_APP_FIELDS_MAY_DEFINE_RELATIONS')
        if expected != set(atom.surfaces):
            raise ValueError('RELATION_MUST_DECLARE_ACTUAL_SURFACES')
    catalog = semantic_catalog(atoms)
    if any(entry['quality'] != 0 for entry in catalog.values()):
        raise ValueError('NO_RELATION_SELECTION_BONUS')
    return atoms


def parameters():
    return {'version': VERSION, 'fitted': False, 'parameter_fit_calls': 0,
            'templates': {a.atom_id: deepcopy(a.provenance) for a in registered_atoms()}}


def relation_cells(source):
    binding = source.get('source_binding') or {}
    if (source.get('status') != 'OK' or binding.get('binding_valid') is not True
            or binding.get('same_app_record') is not True
            or not isinstance(binding.get('app_session_id'), str) or not binding['app_session_id']):
        return {a.atom_id: dict(cell('FAILED', 'CURRENT_APP_SOURCE_BINDING_FAILED'),
                                diagnostics={'source_errors': source.get('errors', [])})
                for a in registered_atoms()}
    result = {**screen.evaluate(source), **resource.evaluate(source)}
    if set(result) != {a.atom_id for a in registered_atoms()}:
        raise ValueError('RELATION_EVALUATOR_REGISTRY_MISMATCH')
    return result


def extend(adapted, source):
    result = deepcopy(adapted)
    cells = relation_cells(source)
    result['raw'].update(cells)
    for atom in registered_atoms():
        measured = cells[atom.atom_id]
        fields = [{'field': field, 'value': deepcopy(source.get('features', {}).get(field)),
                   'value_present': field in source.get('features', {}),
                   'source_status': source.get('field_status', {}).get(field),
                   'source_quality': source.get('field_quality', {}).get(field)}
                  for field in atom.provenance['field_refs']]
        state = ('FAILED' if measured['evaluation_status'] != 'OK' else
                 'U' if not measured['available'] else 'T' if measured['value'] else 'F')
        result['candidate_inputs'][atom.atom_id] = {
            'field_refs': atom.provenance['field_refs'], 'fields': fields, 'state': state,
            'reason': measured['reason'], 'available': measured['available'],
            'evaluation_status': measured['evaluation_status'],
            'diagnostics': deepcopy(measured.get('diagnostics', {})),
            'source_binding': deepcopy(source.get('source_binding', {}))}
    result.update(adapter_version=VERSION, base_adapter_version=old.VERSION,
                  relation_source_status=source.get('status'),
                  relation_source_errors=deepcopy(source.get('errors', [])))
    return result


def _match_source(source, sample_id, session_id):
    binding = source.get('source_binding') or {}
    if binding.get('sample_id') == sample_id and binding.get('app_session_id') == session_id:
        return source
    rejected = deepcopy(source)
    rejected.update(status='FAILED', errors=[*source.get('errors', []), 'PREPARED_RAW_CURRENT_APP_BINDING_MISMATCH'])
    rejected['source_binding'] = dict(binding, binding_valid=False, same_app_record=False)
    return rejected


def adapt_controlled(prepared, source):
    sid = prepared.get('opaque_id')
    session = sid.removeprefix('webgl1fresh-') if isinstance(sid, str) and sid.startswith('webgl1fresh-') else None
    return extend(old.adapt_controlled(prepared), _match_source(source, sid, session))


def adapt_mtc(observation, source):
    return extend(old.adapt_mtc(observation), _match_source(source, observation.get('sample_id'),
                  observation.get('app', {}).get('session_id')))


def registry():
    return {'version': VERSION, 'base_candidate_count': 50,
            'base_definitions_unchanged': True, 'base_adapter_version': old.VERSION,
            'relation_atoms': [asdict(a) for a in registered_atoms()],
            'parameters': parameters(), 'no_source_or_label_features': True}
