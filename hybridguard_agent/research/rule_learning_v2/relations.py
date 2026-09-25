"""Three bounded research relation families; no learned string vocabulary."""
import copy
import json
import math
import re

from hybridguard_agent.research.rule_learning.contracts import cell
from hybridguard_agent.research.rule_learning.fold_data import TrainQuantiles
from hybridguard_agent.research.rule_learning.models import Atom
from .adapter import TrainAccess
from .common import ROOT, OUT as A_OUT, read, write, relative, folds, stamp

VERSION='V2_B_RELATIONS_V1'
N_MEM='app.android_native_data.memory_layer.total_memory_gb'
W_MEM='app.web_data.navigator_layer.device_memory'
N_LANG='app.android_native_data.locale_timezone_layer.native_locale'
W_LANG='app.web_data.navigator_layer.language'
W_LANGS='app.web_data.navigator_layer.languages'
N_TZ='app.android_native_data.locale_timezone_layer.native_timezone_id'
N_OFFSET='app.android_native_data.locale_timezone_layer.native_timezone_offset_min'
W_OFFSET='app.web_data.execution_layer.timezone_offset'
FIELDS=(N_MEM,W_MEM,N_LANG,W_LANG,W_LANGS,N_TZ,N_OFFSET,W_OFFSET)
RATIO='UNFITTED_CONTROL:V2REL.MEMORY_WEB_NATIVE_RATIO'
LANG_PRIMARY='V2REL:LANG_NATIVE_WEB_PRIMARY_DIFFERS'
LANG_LIST='V2REL:LANG_NATIVE_PRIMARY_ABSENT_WEB_LIST'
TZ='V2REL:FIXED_NATIVE_VS_WEB_OFFSET_DIFFERS'
WEB_LIST='V2SINGLE:WEB_PRIMARY_ABSENT_WEB_LIST'


def observed(payload, field):
    if not isinstance(payload,dict): return None
    if payload.get('field_status',{}).get(field)!='observed' or payload.get('field_quality',{}).get(field)!='observed_value':
        return None
    return payload.get('features',{}).get(field)


def positive_number(value):
    return type(value) in (int,float) and math.isfinite(value) and value>0


def memory_ratio(native, web):
    # It is a scale relation, NOT physical RAM equality or a universal browser
    # quantization rule. Kernel RAM and the approximate browser value differ.
    if not (positive_number(native) and positive_number(web)): return None
    ratio=web/native
    return ratio if math.isfinite(ratio) else None


def primary_language(tag):
    """Explicit limited BCP47 syntax; unsupported aliases/extensions stay U."""
    if not isinstance(tag,str): return None
    match=re.fullmatch(r'([A-Za-z]{2,3})(?:-[A-Za-z]{4})?(?:-(?:[A-Za-z]{2}|[0-9]{3}))?',tag)
    if not match: return None
    language=match[1].lower()
    if language in ('und','mul','zxx','iw','in','ji'): return None
    return language


def language_members(tags):
    if not isinstance(tags,list) or not tags: return None
    parsed=[primary_language(x) for x in tags]
    return None if any(x is None for x in parsed) else set(parsed)


def fixed_offset(zone):
    """Minutes east of UTC, only syntactically fixed zones; no date guessing."""
    if not isinstance(zone,str): return None
    if zone in ('GMT','UTC','Etc/UTC','Etc/GMT','Z'): return 0
    match=re.fullmatch(r'(?:(?:GMT|UTC))?([+-])(\d{2}):(\d{2})',zone)
    if match:
        h,m=int(match[2]),int(match[3])
        if h>23 or m>59: return None
        return (1 if match[1]=='+' else -1)*(60*h+m)
    # IANA Etc/GMT uses the POSIX reversed sign.
    match=re.fullmatch(r'Etc/GMT([+-])(\d{1,2})',zone)
    if match and int(match[2])<=14:
        return (-1 if match[1]=='+' else 1)*60*int(match[2])
    return None


def timezone_difference(native_zone,native_raw,web_current):
    minutes=fixed_offset(native_zone)
    if (minutes is None or type(native_raw) not in (int,float) or type(web_current) not in (int,float)
            or not math.isfinite(native_raw) or not math.isfinite(web_current)
            or native_raw!=int(native_raw) or web_current!=int(web_current)
            or abs(web_current)>=1440 or native_raw!=minutes):
        return None
    return minutes != -web_current


def boolean(value, reason):
    return cell('U',reason) if value is None else cell('T' if value else 'F',reason)


def raw_relations(payload,spec):
    families=spec.get('relation_families',[])
    result={}
    if set(families)-{'memory','language','timezone'}: raise ValueError('UNAUTHORIZED_RELATION_FAMILY')
    if 'memory' in families:
        value=memory_ratio(observed(payload,N_MEM),observed(payload,W_MEM))
        result[RATIO]={'value':value,'available':value is not None,'evaluation_status':'OK',
                       'reason':'WEB_APPROXIMATE_GIB_DIVIDED_BY_NATIVE_KERNEL_GIB_NOT_RAM_EQUALITY'}
    if 'language' in families or spec.get('matched_single_features'):
        web=primary_language(observed(payload,W_LANG))
        members=language_members(observed(payload,W_LANGS))
        if 'language' in families:
            native=primary_language(observed(payload,N_LANG))
            result[LANG_PRIMARY]=boolean(None if native is None or web is None else native!=web,'PRIMARY_LANGUAGE_DIFFERENCE_CAN_BE_LEGAL')
            result[LANG_LIST]=boolean(None if native is None or members is None else native not in members,'PROCESS_PRIMARY_NOT_IN_BROWSER_PREFERENCES_CAN_BE_LEGAL')
        if spec.get('matched_single_features'):
            result[WEB_LIST]=boolean(None if web is None or members is None else web not in members,'WEB_ONLY_PRIMARY_MEMBERSHIP_WITH_SAME_PARSER')
    if 'timezone' in families:
        value=timezone_difference(observed(payload,N_TZ),observed(payload,N_OFFSET),observed(payload,W_OFFSET))
        result[TZ]=boolean(value,'FIXED_NATIVE_ZONE_VS_WEB_CURRENT_OFFSET;DYNAMIC_NATIVE_DST_DOMAIN_IS_U')
    return result


def fixed_atoms(spec):
    atoms=[]
    def add(name,family,fields,surfaces,group):
        atoms.append(Atom(name,'V2_'+family,tuple(surfaces),('RESEARCHER_PROPOSED_V2',),(name,),
            'RESEARCH_CONDITION_NOT_ATTACK_TRUTH',{'field_refs':fields,'relation_version':VERSION,'signal_group':group}))
    if 'language' in spec.get('relation_families',[]):
        add(LANG_PRIMARY,'LANGUAGE',[N_LANG,W_LANG],['native84','app_web67'],'language_preferences')
        add(LANG_LIST,'LANGUAGE',[N_LANG,W_LANGS],['native84','app_web67'],'language_preferences')
    if 'timezone' in spec.get('relation_families',[]):
        add(TZ,'TIMEZONE',[N_TZ,N_OFFSET,W_OFFSET],['native84','app_web67'],'timezone_semantics')
    if spec.get('matched_single_features'):
        add(WEB_LIST,'LANGUAGE_WEB',[W_LANG,W_LANGS],['app_web67'],'language_preferences')
    return atoms


def encode_relations(access,payloads,spec,frozen=None):
    if set(payloads)!=set(access.ids): raise PermissionError('EXACT_OWN_TRAIN_RELATION_MEMBERS')
    raw={i:raw_relations(payloads[i],spec) for i in access.ids}
    fixed=fixed_atoms(spec)
    if frozen is None:
        encoder={'version':VERSION,'fold_id':access.fold_id,'train_ids':list(access.ids),'numeric':{},
                 'fixed_atoms':[a.atom_id for a in fixed],'vocabulary_fit':False}
        if 'memory' in spec.get('relation_families',[]):
            derived=TrainAccess(access.job,{i:{RATIO:r[RATIO]} for i,r in raw.items()},access.metadata)
            q=TrainQuantiles(RATIO).fit(derived,derived.batch())
            encoder['numeric'][RATIO]={'thresholds':list(q.thresholds),
                'train_observed_n':sum(r[RATIO]['available'] for r in raw.values()),'train_expected_n':len(raw),
                'atom_ids':['V2REL:MEMORY_WEB_NATIVE_RATIO:LE:'+repr(v) for v in q.thresholds]}
            access.operations.extend(dict(e,derived_scope='MEMORY_RATIO_TRAIN_QUANTILES') for e in derived.operations)
    else:
        encoder=copy.deepcopy(frozen)
        if encoder['version']!=VERSION or encoder['fold_id']!=access.fold_id or encoder['train_ids']!=list(access.ids):
            raise ValueError('RELATION_ENCODER_TRAIN_OR_VERSION_MISMATCH')
        if encoder['fixed_atoms']!=[a.atom_id for a in fixed] or set(encoder['numeric'])!=({RATIO} if 'memory' in spec.get('relation_families',[]) else set()):
            raise ValueError('RELATION_ENCODER_SPEC_MISMATCH')
    atoms=relation_atoms(spec,encoder)
    return {i:evaluate_relations(payloads[i],spec,encoder) for i in access.ids},atoms,encoder


def relation_atoms(spec,encoder):
    atoms=fixed_atoms(spec)
    if RATIO in encoder['numeric']:
        e=encoder['numeric'][RATIO]
        atoms.extend(Atom(name,'V2_MEMORY',('native84','app_web67'),('RESEARCHER_PROPOSED_V2',),(name,),'TRAIN_RATIO_LE',
            {'field_refs':[N_MEM,W_MEM],'threshold':threshold,'threshold_scope':'EXACT_OWN_TRAIN',
             'relation_version':VERSION,'signal_group':'memory_capacity'})
            for name,threshold in zip(e['atom_ids'],e['thresholds'],strict=True))
    return tuple(atoms)


def evaluate_relations(payload,spec,encoder):
    raw=raw_relations(payload,spec)
    result={n:raw[n] for n in encoder['fixed_atoms']}
    for field,e in encoder['numeric'].items():
        value=raw[field]['value']
        for name,threshold in zip(e['atom_ids'],e['thresholds'],strict=True):
            result[name]=boolean(None if value is None else value<=threshold,'TRAIN_FROZEN_MEMORY_RATIO_THRESHOLD')
    return result


def prepare_payload_index():
    out=A_OUT.parent/'B_development'
    source=ROOT/'hybridguard_agent/artifacts/formal_manipulation_v1_20260923/02_inputs/inference_inputs.jsonl'
    wanted={i for f in folds() for i in f['outer_test']};index={}
    # Structural read-only offset index; no parameter/statistic/label is learned.
    with source.open('rb') as stream:
        while True:
            offset=stream.tell();line=stream.readline()
            if not line: break
            r=json.loads(line);oid=r['opaque_id']
            if oid in wanted:
                if oid in index: raise ValueError('DUPLICATE_PAYLOAD_ID')
                index[oid]={'offset':offset,'length':len(line)}
    if set(index)!=wanted: raise ValueError('RELATION_SOURCE_INDEX_INCOMPLETE')
    write(out/'relation_input_index.json',{'version':VERSION,'source':relative(source),'source_bytes':source.stat().st_size,
          'operation':'READ_ONLY_BYTE_OFFSET_INDEX_NO_FIT_NO_LABELS','allowed_fields':list(FIELDS),'members':index})


def relation_fields(spec):
    fields=set()
    for family in spec.get('relation_families',[]):
        fields.update({'memory':(N_MEM,W_MEM),'language':(N_LANG,W_LANG,W_LANGS),
                       'timezone':(N_TZ,N_OFFSET,W_OFFSET)}[family])
    if spec.get('matched_single_features'): fields.update((W_LANG,W_LANGS))
    return tuple(f for f in FIELDS if f in fields)


def load_payloads(ids,fields=FIELDS):
    index=read(A_OUT.parent/'B_development/relation_input_index.json')
    source=ROOT/index['source'];result={}
    if source.stat().st_size!=index['source_bytes']: raise ValueError('RELATION_SOURCE_CHANGED')
    with source.open('rb') as stream:
        for i in ids:
            location=index['members'][i];stream.seek(location['offset']);r=json.loads(stream.read(location['length']))
            if r['opaque_id']!=i: raise ValueError('RELATION_SOURCE_MEMBER_MISMATCH')
            payload=r['payload']
            result[i]={k:{field:payload.get(k,{}).get(field) for field in fields}
                       for k in ('features','field_status','field_quality')}
    return result


def registry():
    return {'version':VERSION,'created_at':stamp(),'role':'RESEARCHER_PROPOSED_V2_NOT_OFFICIAL_ATTACK_DEFINITION',
      'sources':{
        'memory_api':'https://www.w3.org/TR/2026/WD-device-memory-1-20260330/',
        'native_memory':'https://developer.android.com/reference/android/app/ActivityManager.MemoryInfo#totalMem',
        'language_api':'https://html.spec.whatwg.org/multipage/system-state.html#dom-navigator-languages',
        'language_syntax':'https://www.rfc-editor.org/rfc/rfc5646',
        'native_locale':'https://docs.oracle.com/javase/8/docs/api/java/util/Locale.html#getDefault--',
        'native_timezone':'https://docs.oracle.com/javase/8/docs/api/java/util/TimeZone.html#getRawOffset--',
        'web_offset':'https://tc39.es/ecma262/multipage/numbers-and-dates.html#sec-date.prototype.gettimezoneoffset'},
      'collector_refs':['android_app/HybridGuard/featureapp/src/main/java/com/example/hybridguard/featureapp/ExpandedFingerprintCollector.kt:107',
          'android_app/HybridGuard/featureapp/src/main/java/com/example/hybridguard/featureapp/ExpandedFingerprintCollector.kt:176',
          'web_probe/canonical_web_probe.js:348','web_probe/canonical_web_probe.js:401'],
      'families':[
        {'id':'memory','status':'IMPLEMENTED_TRAIN_RATIO','fields':[N_MEM,W_MEM],'units':'GiB/GiB dimensionless; Native totalMem excludes below-kernel fixed allocations, Web is approximate/quantized/clamped',
         'expression':'Web device_memory / Native total_memory_gb, with <= own train Q25/Q50/Q75 and both original polarities',
         'parameters':'Only original linear train quantiles; no universal equality, clamp constant, or all-development cutpoint',
         'domain':'Finite positive numeric values, both observed_value; missing/zero/boolean/invalid -> U',
         'legal_counterexamples':['2.4145 GiB -> Web 2 by quantization','6 GiB -> Web 8 by rounding','32 GiB -> Web 8 by an implementation cap','Kernel reserved memory, VM/container limits and browser privacy policy'],
         'limitation':'This is a learned scale contrast, not proof that RAM values must coincide. No history/APK execution or universal quantizer was inferred.',
         'second_source_value_dependency':True,'matched_single_information':'Both raw numeric fields already present in S_FLAT; W0 has Web memory. No new memory single-field parsing.'},
        {'id':'language','status':'IMPLEMENTED_LIMITED_PRIMARY_SUBTAG_RELATIONS','fields':[N_LANG,W_LANG,W_LANGS],
         'expressions':[LANG_PRIMARY,LANG_LIST],'parameters':'No learned vocabulary. Case-insensitive 2/3-letter primary, optional script and region; variants/extensions/private-use/deprecated unresolved forms -> U.',
         'units':'Primary subtag only, not full locale identity or linguistic mutual intelligibility',
         'legal_counterexamples':['en-US vs en-GB same primary','Reordered/fallback language lists','Process locale en-US and browser preference fr-FR can be legitimate','Scripts can matter even with the same primary'],
         'matched_single_atom':WEB_LIST,'matched_single_inputs':[W_LANG,W_LANGS],
         'matched_single_parameters':'Identical parser and set membership. No Native input, arbitrary category dictionary or training vocabulary.',
         'second_source_value_dependency':True},
        {'id':'timezone','status':'IMPLEMENTED_FIXED_NATIVE_DOMAIN_ONLY','fields':[N_TZ,N_OFFSET,W_OFFSET],
         'expression':TZ,'units':'Native minutes east, Web Date minutes west; negate Web before comparing',
         'parameters':'Known fixed-zone syntax/UTC aliases; Native ID offset must agree with Native raw offset',
         'domain':'Dynamic Native zones/DST, unsupported names or inconsistent Native fields -> U. For fixed Native zones no timestamp is needed; Web offset already represents its actual current instant.',
         'legal_counterexamples':['GMT, UTC and +00:00 aliases','Separate process/browser zones can legitimately differ','Dynamic-zone raw standard offset differs from DST current offset'],
         'blocked':'General dynamic Native-zone relation needs a trustworthy observation instant/current offset; it is not approximated by rawOffset.',
         'second_source_value_dependency':True,'matched_single_information':'Web numeric offset already present; no Web zone vocabulary is added.'}],
      'blocked_extensions':['Native/Host CPU count absent; ABI is not a count','Plugins/MIME have no second-source member mirror; hashes excluded'],
      'data_dependence':'Only the ratio encoder fits own-fold train. Pure parsing/indexing never fits; no calibration on all 162 stages.'}
