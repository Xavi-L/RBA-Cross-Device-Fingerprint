"""Predeclared fixed-model responses; fixtures never receive real clean labels."""
import copy
import hashlib
import time
from pathlib import Path

from hybridguard_agent.research.rule_learning.contracts import cell, ledger
from hybridguard_agent.research.rule_learning.matrix import extract_atom, control_input, mask
from hybridguard_agent.research.rule_learning.predictor import predict
from .common import ROOT,V1,read,write,write_lines,definitions,stamp,relative
from .b_engine import selected_definitions
from .adapter import approved_atoms
from . import c_engine

ROLE='SYNTHETIC_SEMANTIC_OR_STRUCTURAL_PROBE'
W='app.web_data.'
N='app.android_native_data.'
H='app.webview_data.'
UA='Mozilla/5.0 (Linux; Android 13; Pixel 7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/110.0.0.0 Mobile Safari/537.36'
DESKTOP='Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/110.0.0.0 Safari/537.36'


def specification():
    cases=[]
    def add(name,changes,why,consistent,status_changes=None):
        cases.append({'id':name,'level':'RAW_COLLECTED_FIELDS_THROUGH_ORIGINAL_MEASUREMENT',
          'changed_fields':changes,'related_fields_kept_consistent':consistent,'why_validate_on_real_normals':why,
          'status_changes':status_changes or {},'limits':'Manually constructed partial field fixture; not a collected device or adjudicated clean sample. Feasibility depends on actual device/browser/version; unprovided fields stay U.'})
    add('baseline_partial_android',{},'Reference for paired structural responses, not a normal truth label.','Android UA/platform, first language, memory scale and signed timezone fields agree.')
    add('higher_memory',{W+'navigator_layer.device_memory':8,N+'memory_layer.total_memory_gb':7.5},'Legitimate hardware RAM and browser approximation may cross an absolute Web threshold.','Native accessible memory and Web approximate capacity changed together; no equality claim.')
    add('higher_cpu',{W+'navigator_layer.hardware_concurrency':8},'Legitimate logical processor counts vary.','No Native/Host CPU count was invented; all existing other fields fixed.')
    add('multiple_languages',{W+'navigator_layer.languages':['en-US','fr-FR']},'Users can add browser language preferences.','Web language remains first list entry en-US; Native locale unchanged.')
    add('changed_language_order',{W+'navigator_layer.language':'fr-FR',W+'navigator_layer.languages':['fr-FR','en-US']},'Process and browser preferences may differ; first preferred language should follow order.','Web language and first list element changed together; Native locale may legitimately differ.')
    add('pdf_mime_capability',{W+'automation_surface_layer.plugins_count':5,W+'automation_surface_layer.mime_types_count':2},'PDF/plugin support can change between legitimate browser implementations.','Counts changed together; no missing plugin/MIME member list or Native mirror invented; actual count behavior requires measurement.')
    add('ua_brand_suffix',{W+'navigator_layer.user_agent':UA+' MyApp/1.0',H+'webview_settings_layer.settings_user_agent':UA+' MyApp/1.0'},'An application may brand its UA while preserving mobile/platform semantics.','Current Web UA and host configured UA agree; host default UA and hardware platform remain original.')
    add('desktop_request_ua',{W+'navigator_layer.user_agent':DESKTOP,H+'webview_settings_layer.settings_user_agent':DESKTOP},'A user-authorized desktop-site compatibility UA can advertise desktop semantics on mobile hardware.','Actual platform remains Android/Linux; configured/current UA changed together. This is declared content negotiation, not an assertion of x86 hardware; actual WebView support remains unverified.')
    add('authorized_webdriver',{W+'automation_surface_layer.webdriver':True},'Authorized automation is not automatically an attack under a general normal-use definition.','Other browser fields unchanged; authorization is scenario metadata, never a predictor.')
    add('timezone_minutes_west',{W+'execution_layer.timezone_offset':60,N+'locale_timezone_layer.native_timezone_id':'GMT-01:00',N+'locale_timezone_layer.native_timezone_offset_min':-60},'Legitimate timezones can have positive Web minutes west.','Native fixed zone and minutes east agree with negated Web minutes west; no DST assumption.')
    add('timezone_minutes_east',{W+'execution_layer.timezone_offset':-480,N+'locale_timezone_layer.native_timezone_id':'GMT+08:00',N+'locale_timezone_layer.native_timezone_offset_min':480},'Response can differ for the other side of zero.','Same instant-compatible fixed timezone sign/unit convention.')
    add('missing_memory',{W+'navigator_layer.device_memory':None},'Missing browser capability must preserve U.','All other fields unchanged; this tests unavailable measurement, not an attack or normal-rate label.',{W+'navigator_layer.device_memory':['unsupported_by_os','source_unavailable']})
    add('invalid_measurement_status',{},'Malformed measurement envelopes must retain execution failure.','Other values unchanged; deliberately invalid engineering input, not a proposed real clean scenario.',{W+'navigator_layer.device_memory':['INVALID_STATUS','observed_value']})
    add('missing_native_anchor',{N+'build_fingerprint_layer.os_version':None},'A missing Native validity anchor can remove coverage for C0.','Web values unchanged; unavailable reference is not proof of attack.',{N+'build_fingerprint_layer.os_version':['unsupported_by_os','source_unavailable']})
    add('invalid_native_anchor_status',{},'Check execution failure on C0 selected Native-dependent conditions.','Deliberately invalid engineering status; no real clean label.',{N+'build_fingerprint_layer.os_version':['INVALID_STATUS','observed_value']})
    for name in ['one_unknown_all_other_literals_false','true_or_unknown','failed_even_with_true']:
        cases.append({'id':name,'level':'PRECOMPUTED_ATOM_LOGIC_ONLY','changed_fields':[],
          'related_fields_kept_consistent':'No raw field realization asserted; selected atom states are prescribed solely for logic.',
          'why_validate_on_real_normals':'Clarify frozen U/failure behavior; cannot establish a real-world error rate.',
          'limits':'Atom-level counterfactual may lack a jointly realizable raw record; never reported as a raw-field test or normal example.'})
    return {'version':'C_STRUCTURAL_PROBES_V1','role':ROLE,'declared_before_C_results':True,
            'source_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'cases':cases,
            'not_real_labels':True,'not_added_to_supervised_metrics':True,'no_fit_or_parameter_selection':True}


def payload_for(case):
    features={W+'navigator_layer.device_memory':2,N+'memory_layer.total_memory_gb':2.4,
       W+'navigator_layer.hardware_concurrency':4,W+'navigator_layer.language':'en-US',W+'navigator_layer.languages':['en-US'],
       W+'navigator_layer.user_agent':UA,W+'navigator_layer.platform':'Linux armv8l',W+'navigator_layer.max_touch_points':5,
       W+'automation_surface_layer.webdriver':False,W+'automation_surface_layer.plugins_count':0,W+'automation_surface_layer.mime_types_count':0,
       W+'execution_layer.timezone_offset':0,N+'build_fingerprint_layer.os_version':'13',N+'build_fingerprint_layer.device_model':'Pixel 7',
       N+'locale_timezone_layer.native_locale':'en-US',N+'locale_timezone_layer.native_timezone_id':'GMT',N+'locale_timezone_layer.native_timezone_offset_min':0,
       H+'kernel_container_layer.default_ua_native':UA,H+'webview_settings_layer.settings_user_agent':UA,
       W+'screen_layer.color_depth':24,W+'screen_layer.pixel_depth':24,W+'screen_layer.device_pixel_ratio':3,
       W+'screen_layer.screen_resolution_logical':'360x800',N+'screen_display_layer.screen_resolution_physical':'1080x2400'}
    features.update(case['changed_fields'])
    p={'record_schema_version':'hybridguard-mtc-observation-v2','adapter_version':'app177-triplet-adapter-v1',
       'features':features,'field_status':{k:'observed' for k in features},'field_quality':{k:'observed_value' for k in features}}
    for k,(status,quality) in case['status_changes'].items():p['field_status'][k]=status;p['field_quality'][k]=quality
    return p


def measure(payload):
    defs=definitions();atoms=approved_atoms(selected_definitions(defs,'W0'))
    fields={s['field']:s for s in read(V1/'R01_protocol/SINGLE_SURFACE_FIELDS.json')['fields']}
    candidates={c['atom_id']:c for c in ledger()}
    catalog={r['rule_id']:r for r in read(ROOT/'hybridguard_agent/config/paired244_rule_catalog.v3.json')['rules']}
    names={a.atom_id for a in atoms}|{c['atom_id'] for c in candidates.values() if c['candidate_use']['core'] and c['candidate_use']['selectable_on_App177']}
    raw={}
    for name in names:
        if name.startswith('CAT:'):
            c=candidates[name];raw[name]=extract_atom(c,catalog[c['rule_id']],payload)
        else:
            a=next(a for a in atoms if a.atom_id==name);spec=fields[a.provenance['field']]
            r=control_input(mask(payload,[spec['surface']]),spec)
            if a.orientation!='UNFITTED_NUMERIC_MEASUREMENT':
                state=None if r['evaluation_status']=='FAILED' else 'U' if not r['available'] else 'T' if r['value']==a.provenance['equals'] else 'F'
                r.update(state=state,value={'T':True,'F':False}.get(state))
            raw[name]=r
    return raw


def run(destination):
    started=time.monotonic();plan=read(destination/'STRUCTURAL_PROBE_PLAN.json')
    if plan['source_sha256']!=hashlib.sha256(Path(__file__).read_bytes()).hexdigest():raise ValueError('PREDECLARED_PROBE_IMPLEMENTATION_CHANGED')
    contract=read(destination/'C_CONTRACT.json');rows=[]
    jobs=[j for j in contract['jobs'] if j['track']=='FINAL_DEVELOPMENT_FIT']
    models={j['spec_id']:c_engine.load_model(destination/'trials'/(j['job_id']+'__attempt01')/'model.json') for j in jobs}
    for case in plan['cases']:
        raw=measure(payload_for(case)) if case['level'].startswith('RAW_') else None
        for spec,model in models.items():
            if raw is not None:
                projected=c_engine.project_inputs({'fixture':raw},definitions(),model.view['representation'])['fixture']
                result=c_engine.predict_current(model,'synthetic:'+case['id'],projected)
            else:
                if case['id'] in ('true_or_unknown','failed_even_with_true') and len(model.clauses)<2:
                    rows.append(dict(case,role=ROLE,spec_id=spec,model_id=model.model_id,decision=None,
                         triggered_clauses=[],failure_reason=None,atom_explanations=[],
                         status='NOT_APPLICABLE_REQUIRES_TWO_SELECTED_CLAUSES',no_real_clean_or_attack_label=True))
                    continue
                encoded={l.atom_id:cell('F' if l.polarity=='POSITIVE' else 'T') for c in model.clauses for l in c.literals}
                chosen=list(model.clauses)
                if chosen:
                    first=chosen[0].literals[0];encoded[first.atom_id]=cell('U')
                    if case['id'] in ('true_or_unknown','failed_even_with_true'):
                        last=chosen[-1].literals[0];encoded[last.atom_id]=cell('T' if last.polarity=='POSITIVE' else 'F')
                    if case['id']=='failed_even_with_true':encoded[first.atom_id]=cell('FAILED')
                result=predict(model,'synthetic:'+case['id'],{'features':encoded,'view_id':model.view['view_id']})
            rows.append(dict(case,role=ROLE,spec_id=spec,model_id=model.model_id,decision=result['decision'],
                 triggered_clauses=[c['clause_id'] for c in result['clause_explanations'] if c['state']=='T'],
                 failure_reason=result['failure_reason'],atom_explanations=result['atom_explanations'],
                 no_real_clean_or_attack_label=True))
    write_lines(destination/'structural_responses.jsonl',rows)
    write(destination/'structural_probe_summary.json',{'role':ROLE,'cases':len(plan['cases']),'model_responses':len(rows),
         'actual_fit_invocations':0,'elapsed_seconds':time.monotonic()-started,'real_FPR':None,
         'limits':'Synthetic function responses only. Even an alert on a proposed legitimate change does not establish its observed frequency or physical realizability.'})
    return rows
