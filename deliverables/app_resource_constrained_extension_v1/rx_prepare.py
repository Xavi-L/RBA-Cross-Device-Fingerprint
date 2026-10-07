"""Build a common index from exact frozen positions; no selection."""
from rx_common import *
import rx_sources as s
RESOURCE_FAMILIES={'A_APP_RESOURCE':'App_resource16_48','A_APP_MEMORY4':'App_memory4',
    'A_BROWSER_RESOURCE':'Browser_resource16_48','A_BROWSER_MEMORY4':'Browser_memory4'}
def members():
    ms=s.old_members()
    for line,p in enumerate(rows(RESOURCE/'results/positions.jsonl'),1):
        e=p['effect'];identity='EFFECTIVE_INTERVENTION' if p['identity']=='CONTROLLED_INTERVENTION' and e['effective'] else p['identity']
        ms.append(dict(sample_id='resource54:'+p['sample_id'],original_alias=p['sample_id'],cohort='resource54',role='selection',
            identity=identity,family=RESOURCE_FAMILIES.get(p['scenario']),scenario=p['scenario'],phase=p['phase'],round=p['round'],
            group_id=f"resource54:{p['scenario']}:{p['round']}",effect=e,
            source_reference=str((RESOURCE/'results/positions.jsonl').relative_to(ROOT))+':'+str(line)))
    index(ms);require(len(ms)==1005,'EXACT_1005_MEMBERS')
    train=[m for m in ms if m['role']=='selection']
    require(len(train)==744 and Counter(m['identity'] for m in train)=={'NORMAL':718,'EFFECTIVE_INTERVENTION':26},'SELECTION_IDENTITIES')
    require(Counter(m['cohort'] for m in ms)=={'mtc_discovery':630,'mtc_development':144,'mtc_reserved_validation':117,'pilot18':18,'b2b42':42,'resource54':54},'COHORT_MEMBERSHIP')
    return ms
def prepare(ms,bases,audit):
    l=s.legacy();old=index(rows(OLD/'results/inputs.jsonl'))
    oldpred=index(rows(OLD/'results/predictions.jsonl'),lambda r:(r['sample_id'],r['model_id']))
    oldms=index(rows(OLD/'results/members.jsonl'))
    require(set(old)==set(oldms),'OLD_INPUT_EXACT_MEMBERS')
    require(set(oldpred)=={(sid,b['model_id']) for sid in oldms for b in bases},'OLD_BASE_EXACT_CARTESIAN')
    mtcm=index(rows(RESOURCE/'results/mtc_members.jsonl'))
    mtcr=index(rows(RESOURCE/'results/mtc_conditions.jsonl'),lambda r:(r['sample_id'],r['condition']))
    rp=index(rows(RESOURCE/'results/positions.jsonl'));rc=index(rows(RESOURCE/'results/conditions.jsonl'),lambda r:(r['sample_id'],r['condition']))
    apppred=index([r for r in rows(RESOURCE/'results/model_predictions.jsonl') if r['scheme']=='APP_FULL'],lambda r:(r['sample_id'],r['model_id']))
    allconditions=set(l.rc.DEPS)
    require(set(mtcr)=={(sid,c) for sid in mtcm for c in allconditions},'MTC_SIX_CONDITION_CARTESIAN')
    require(set(rc)=={(sid,c) for sid in rp for c in allconditions},'RESOURCE_SIX_CONDITION_CARTESIAN')
    require(set(apppred)=={(sid,b['base_model_id']) for sid in rp for b in bases},'RESOURCE_FULL_MODEL_CARTESIAN')
    inputs=[];new_outputs=[];bindings=[]
    for m in ms:
        sid=m['sample_id'];refs={};appstates={};bs={}
        if m['cohort']=='resource54':
            alias=m['original_alias'];p=rp[alias]
            a,br,prov=s.raw_v16(m);prepared=s.prepare_v16(a,br,prov)
            require(not any(prepared['errors'].values()),'NEW_RESOURCE_PAIR_INVALID')
            cr=l.c1.evaluate('C1',prepared['pair']);audit['new_C1_evaluations']+=1
            new_outputs.append(dict(sample_id=sid,condition='C1',**cr));c1=cr['state']
            for b in bases:
                pred=apppred[alias,b['base_model_id']]
                require(all(pred[k]==p[k] for k in ('scenario','round','phase','identity','cohort')),'RESOURCE_APP_META_CHANGED')
                require(pred['fold']==b['base']['fold'],'RESOURCE_APP_FOLD_CHANGED')
                expected=[c.id for c in l.rd.APP.full_models()[b['base']['fold']].clauses]
                require([c['clause_id'] for c in pred['rules']]==expected,'RESOURCE_APP_RULES_CHANGED')
                appstates[b['model_id']]=pred['state'];bs[b['model_id']]=combine(pred['state'],{'C1':c1},['C1'])
                audit['reused_resource_app_states']+=1;audit['new_resource_base_combinations']+=1
            cond={}
            for cid,name in CANDIDATES.items():
                r=rc[alias,name];require(all(r[k]==p[k] for k in ('scenario','round','phase','identity','cohort')),'RESOURCE_CONDITION_META')
                require(r['operands']=={f:prepared['record']['features'].get(f) for f in l.rc.DEPS[name]},'RESOURCE_OPERAND_MISMATCH')
                cond[cid]=r['state'];audit['reused_resource_candidate_states']+=1
            refs.update(base=str((RESOURCE/'results/model_predictions.jsonl').relative_to(ROOT)),conditions=str((RESOURCE/'results/conditions.jsonl').relative_to(ROOT)),C1='new_conditions.jsonl')
        else:
            row=old[sid];c1=row['conditions']['C1']
            savedc=s.physical(row['references']['conditions']['C1'])
            require(savedc['meta']==m['source_meta'] and savedc['condition_id']=='C1' and savedc['state']==c1,'OLD_C1_IDENTITY')
            for b in bases:
                pr=oldpred[sid,b['model_id']];appstate=row['base_states'][b['base_model_id']]
                require(pr['base_model_id']==b['base_model_id'] and pr['base_state']==appstate and pr['selected_conditions']=={'C1':c1},'OLD_BASE_MODEL_IDENTITY')
                rawpr=s.physical(row['references']['base'][b['base_model_id']]);rawpr=rawpr.get('prediction',rawpr)
                require(rawpr['model_id']==b['base_model_id'],'ORIGINAL_APP_MODEL_ID')
                require(l.b2.selection is l.rd.APP.full_engine,'ORIGINAL_APP_ENGINE')
                original_state=rawpr.get('logical_state') or rawpr['decision']
                require(original_state==appstate,'ORIGINAL_APP_STATE_CHANGED')
                require(pr['state']==combine(appstate,{'C1':c1},['C1']),'OLD_BASE_OR_MISMATCH')
                appstates[b['model_id']]=appstate;bs[b['model_id']]=pr['state'];audit['reused_old_base_states']+=1
            if m['cohort'].startswith('mtc_'):
                meta=mtcm[sid]
                for key in ('sample_id','group','evaluation_basis','pair_reference','app_reference','browser_reference','normal_basis'):
                    require(meta[key]==m['source_meta'][key],'MTC_SOURCE_IDENTITY:'+key)
                cond={}
                for cid,name in CANDIDATES.items():
                    r=mtcr[sid,name];require(r['group']==meta['group'] and r['identity']=='NORMAL' and r['cohort']=='mtc','MTC_CANDIDATE_GROUP')
                    cond[cid]=r['state'];audit['reused_MTC_candidate_states']+=1
                refs['conditions']=str((RESOURCE/'results/mtc_conditions.jsonl').relative_to(ROOT))
            else:
                a,br,prov=s.raw_v16(m);prepared=s.prepare_v16(a,br,prov)
                six=l.rc.evaluate(prepared['record']);audit['new_resource_evaluate_calls']+=1;audit['new_resource_condition_calls']+=6
                cond={cid:six[name]['state'] for cid,name in CANDIDATES.items()}
                new_outputs.extend(dict(sample_id=sid,condition=name,**value) for name,value in six.items())
                bindings.append(dict(sample_id=sid,errors=prepared['errors'],raw_source=m['source_meta']))
                refs['conditions']='new_conditions.jsonl'
            refs.update(base=str((OLD/'results/predictions.jsonl').relative_to(ROOT)),original_inputs=row['references'])
        inputs.append(dict(sample_id=sid,cohort=m['cohort'],role=m['role'],identity=m['identity'],base_states=bs,app_states=appstates,C1=c1,conditions=cond,references=refs))
    validate(ms,inputs,[b['model_id'] for b in bases])
    return inputs,new_outputs,bindings
