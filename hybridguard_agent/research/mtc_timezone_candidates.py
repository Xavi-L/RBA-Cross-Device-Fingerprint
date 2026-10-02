"""Explicit 50 + two existing relations + one timezone relation representation."""
from copy import deepcopy
from dataclasses import asdict
from . import mtc_relation_candidates as prior
from . import mtc_reselection_candidates as old
from . import mtc_timezone_relation as tz
from .rule_learning_v2.semantic_selection import semantic_catalog

VERSION = 'mtc-timezone-candidate-adapter-v1'


def registered_atoms():
    atoms = (*prior.registered_atoms(), *tz.registered_atoms())
    if len(tz.registered_atoms()) != 1 or len(atoms) != 3:
        raise ValueError('EXACTLY_ONE_NEW_TIMEZONE_TEMPLATE')
    if any(c['quality'] != 0 for c in semantic_catalog(atoms).values()):
        raise ValueError('NO_CROSS_SURFACE_BONUS')
    return atoms


def parameters():
    return {'version': VERSION, 'fitted': False, 'parameter_fit_calls': 0,
            'templates': {a.atom_id: deepcopy(a.provenance) for a in registered_atoms()},
            'timezone': tz.parameters()}


def extend(adapted, source):
    result = prior.extend(adapted, source)
    cells = tz.evaluate(source)
    result['raw'].update(cells)
    for atom in tz.registered_atoms():
        c = cells[atom.atom_id]
        result['candidate_inputs'][atom.atom_id] = {
            'field_refs': atom.provenance['field_refs'],
            'fields': [{'field':f,'value':deepcopy(source.get('features',{}).get(f)),
                        'value_present':f in source.get('features',{}),
                        'source_status':source.get('field_status',{}).get(f),
                        'source_quality':source.get('field_quality',{}).get(f)}
                       for f in atom.provenance['field_refs']],
            'state': 'FAILED' if c['evaluation_status'] != 'OK' else 'U' if not c['available'] else 'T' if c['value'] else 'F',
            'reason':c['reason'], 'available':c['available'], 'evaluation_status':c['evaluation_status'],
            'diagnostics':deepcopy(c.get('diagnostics',{})),
            'source_binding':deepcopy(source.get('source_binding',{}))}
    result.update(adapter_version=VERSION,base_relation_adapter_version=prior.VERSION)
    return result


def adapt_controlled(prepared, source):
    sid=prepared.get('opaque_id')
    session=sid.removeprefix('webgl1fresh-') if isinstance(sid,str) and sid.startswith('webgl1fresh-') else None
    return extend(old.adapt_controlled(prepared), prior._match_source(source,sid,session))


def adapt_mtc(observation, source):
    return extend(old.adapt_mtc(observation), prior._match_source(source,observation.get('sample_id'),
                    observation.get('app',{}).get('session_id')))


def registry():
    return {'version':VERSION,'base_candidate_count':50,'old_relation_count':2,'new_relation_count':1,
            'base_definitions_unchanged':True,'old_relations_unchanged':True,
            'relation_atoms':[asdict(a) for a in registered_atoms()], 'parameters':parameters(),
            'date_usage':'timezone conversion only; not numeric encoding or identity features'}
