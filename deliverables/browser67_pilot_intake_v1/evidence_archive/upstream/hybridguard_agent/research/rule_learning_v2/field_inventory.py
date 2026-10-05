"""Three proposed research families, verified against observed fields and code.
No proposed relation is made into a candidate or fitted in V2-A.
"""
from collections import Counter
from .common import *
from .diagnose import metadata, RAW_REF

N = 'app.android_native_data.'
W = 'app.web_data.'
COLLECTOR = 'android_app/HybridGuard/featureapp/src/main/java/com/example/hybridguard/featureapp/ExpandedFingerprintCollector.kt'
PROBE = 'web_probe/canonical_web_probe.js'


def main():
    meta = metadata()
    payloads = {r['opaque_id']: r['payload'] for r in lines(ROOT / RAW_REF) if r['opaque_id'] in meta}
    catalog = ROOT / 'android_app/HybridGuard/featureapp/src/main/assets/expanded_v2_field_catalog.csv'
    def observed(field):
        if field is None: return {'exists': False, 'observed_n': 0, 'n': 162, 'values': {}}
        return {'exists': any(field in p['features'] for p in payloads.values()), 'n': 162,
                'observed_n': sum(p['field_status'].get(field)=='observed' and p['field_quality'].get(field)=='observed_value' for p in payloads.values()),
                'values': dict(Counter(json.dumps(p['features'].get(field),ensure_ascii=False) for p in payloads.values()))}
    directions = [
        ('RESOURCE_CAPABILITY', 'memory', N+'memory_layer.total_memory_gb', W+'navigator_layer.device_memory',
         'REAL_REFERENCE_SEMANTIC_ALIGNMENT_REQUIRED',
         'Native totalMem / 1024^3 is GiB despite _gb name; Web deviceMemory is an approximate, rounded/clamped exposure, not exact RAM.',
         'Healthy 2.4145 GiB Native versus Web 2 is already present. Browser rounding, clamps, unavailable APIs and process/environment limits are legitimate counterexamples to equality.',
         'A later version may test a semantic range/residual; first bind units and actual browser-version behavior. No new bound implemented here.',
         [COLLECTOR+':107', COLLECTOR+':451', PROBE+':355', 'https://www.w3.org/TR/device-memory/']),
        ('RESOURCE_CAPABILITY','logical_processors',None,W+'navigator_layer.hardware_concurrency',
         'BLOCKED_MISSING_NATIVE_HOST_REFERENCE',
         'Web logical processors potentially available to user agent; CPU ABI/architecture is not a count.',
         'Browser worker limits and anti-fingerprinting can lower reported concurrency; >4 is not an attack definition.',
         'Keep existing single-field pilot result; any Native CPU-count collection requires separate authorization.',
         [str(catalog.relative_to(ROOT)),COLLECTOR+':80',PROBE+':354','https://html.spec.whatwg.org/multipage/workers.html#dom-navigator-hardwareconcurrency']),
        ('LANGUAGE_LIST','locale_and_language_preferences',N+'locale_timezone_layer.native_locale',W+'navigator_layer.languages',
         'REAL_REFERENCE_LEGAL_VARIATION_UNRESOLVED',
         'Native Locale.getDefault().toLanguageTag() is process default; Web languages is an ordered array. V1 numeric control retains only length.',
         'Application/process locale, browser language preferences, fallback language tags and ordering can legitimately differ. en-US,en still includes native en-US.',
         'Consider a bounded language-family/set relation after authorizing B and agreeing legitimate customization cases; no arbitrary string vocabulary.',
         [COLLECTOR+':176',PROBE+':349','hybridguard_agent/research/rule_learning/matrix.py:357']),
        ('LANGUAGE_LIST','primary_language',N+'locale_timezone_layer.native_language',W+'navigator_layer.language',
         'REAL_REFERENCE_UNITS_REQUIRE_TAG_NORMALIZATION',
         'Native language subtag en versus Web full tag en-US; raw equality has mismatched granularity.',
         'Regional variants and per-application language are legitimate; current language field stays en-US even in French languages-list intervention.',
         'Keep as explanatory evidence; any new normalization grammar is B-only.',[COLLECTOR+':177',PROBE+':348']),
        ('LANGUAGE_LIST','plugin_mime_counts',None,W+'automation_surface_layer.mime_types_count',
         'BLOCKED_MISSING_NATIVE_HOST_REFERENCE_AND_MEMBER_LIST',
         'Counts exist; source computes local member summaries but saves only counts and hashes, not semantic member lists.',
         'PDF support, browser builds and authorized automation can change counts. Hashes do not supply a lawful Native mirror or permitted vocabulary.',
         'Retain same-surface controls; do not use hashes or invent Native plugin membership.',[PROBE+':583',PROBE+':607',str(catalog.relative_to(ROOT))]),
        ('TIMEZONE','offset',N+'locale_timezone_layer.native_timezone_offset_min',W+'execution_layer.timezone_offset',
         'REAL_REFERENCE_BLOCKED_FOR_GENERAL_RULE_BY_DST_AND_SIGN',
         'Native rawOffset/60000 is standard-time local-minus-UTC minutes without DST; JavaScript getTimezoneOffset is UTC-minus-local at current date.',
         'DST, different sampling instant near transitions and legitimate per-process/browser timezone changes invalidate simple equality or sign reversal.',
         'Resolve current-time/DST semantics and allowed customization before a B predicate. Existing GMT-only data cannot validate nonzero/DST cases.',
         [COLLECTOR+':180',PROBE+':401','https://docs.oracle.com/javase/8/docs/api/java/util/TimeZone.html#getRawOffset--']),
        ('TIMEZONE','zone_identifier',N+'locale_timezone_layer.native_timezone_id',W+'execution_layer.timezone_id',
         'REAL_REFERENCE_LEGAL_ALIAS_VARIATION_UNRESOLVED',
         'Native TimeZone ID and Intl resolved ID can use aliases/offset strings. Current clean contains GMT versus UTC/+00:00.',
         'Distinct IDs can identify the same offset; equal current offsets can have different DST rules.',
         'Do not learn literal zone IDs. Bind semantic equivalence and date if later authorized.',[COLLECTOR+':179',PROBE+':398'])
    ]
    rows=[]
    for family,component,native,web,status,units,counterexample,action,refs in directions:
        example_ids=[i for i,m in meta.items() if m['phase']=='attack' and (
            ('RESOURCE' in family and ('resource-pair' in m['config_id'] or '058' in m['config_id'])) or
            (family=='LANGUAGE_LIST' and any(s in m['config_id'] for s in ('languages','plugins','058'))) or
            (family=='TIMEZONE' and 'timezone' in m['config_id']))]
        rows.append({'family':family,'component':component,'native_field':native,'web_field':web,
            'host_field':None,'host_reference_status':'NO_SAME_SEMANTIC_REFERENCE_IN_HOST26',
            'status':status,'native_observation':observed(native),'web_observation':observed(web),
            'units_and_meaning':units,'legal_counterexamples':counterexample,'next_action':action,
            'evidence_paths':refs+[RAW_REF+'#opaque_id='+i for i in example_ids], 'new_predicate_implemented':False})
    write_csv(OUT/'field_reference_inventory.csv',rows)
    write(OUT/'field_reference_inventory.json',{'prioritized_families':3,'rows':rows,
        'native_cpu_count_search':{'registered_catalog_matches':[],
            'actual_native_processor_like_fields':sorted({f for p in payloads.values() for f in p['features']
                if f.startswith(N) and any(x in f.lower() for x in ('cpu','core','processor','abi','arch'))}),
            'interpretation':'Existing ABI/architecture fields are not concurrency counts; no mirror invented.'},
        'measurement_scope':'162 S01 supervised stages; 100 descriptive stages not fitted or promoted',
        'source_version_caution':'Local collector source explains current field semantics; it is not an APK-byte reproduction or new collection audit.',
        'priority_is_development_hypothesis_not_performance_promise':True})
    print('Saved 3 families / 7 field-reference entries; no new predicate.')


if __name__=='__main__': main()
