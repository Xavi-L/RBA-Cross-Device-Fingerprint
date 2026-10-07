"""Six preregistered resource conditions; no labels, controls, fitting or network."""
import math
from hybridguard_agent.research import mtc_resource_relations as original
N=original.NATIVE_MEMORY
A=original.WEB_MEMORY
B='browser.web_data.navigator_layer.device_memory'
AC='app.web_data.navigator_layer.hardware_concurrency'
BC='browser.web_data.navigator_layer.hardware_concurrency'
DEPS={'R_APP_MEMORY':(N,A),'R_NATIVE_BROWSER_MEMORY':(N,B),'R_WEB_MEMORY_DIFFERENCE':(A,B),
      'D_APP_MEMORY8':(A,),'D_BROWSER_MEMORY8':(B,),'D_CPU_DIFFERENCE':(AC,BC)}
BINDINGS={'R_APP_MEMORY':('app',),'R_NATIVE_BROWSER_MEMORY':('app','browser','pair'),
          'R_WEB_MEMORY_DIFFERENCE':('app','browser','pair'),'D_APP_MEMORY8':('app',),
          'D_BROWSER_MEMORY8':('browser',),'D_CPU_DIFFERENCE':('app','browser','pair')}

def operand(record,field):
    value=record.get('features',{}).get(field)
    if field not in record.get('features',{}):return None,'MISSING'
    if record.get('field_status',{}).get(field)!='observed' or record.get('field_quality',{}).get(field)!='observed_value':return None,'QUALITY_UNAVAILABLE'
    if type(value) not in (int,float) or not math.isfinite(value) or value<=0:return None,'INVALID_OR_DEFAULT'
    if field in (AC,BC) and (not float(value).is_integer()):return None,'CPU_NOT_INTEGER'
    return value,None

def evaluate(record):
    out={}
    for name,fields in DEPS.items():
        evidence={'dependencies':list(fields),'operands':{f:record.get('features',{}).get(f) for f in fields}}
        errors=[side for side in BINDINGS[name] if record.get('binding',{}).get(side) is not True]
        field_errors=[f for f in fields if f in record.get('field_errors',{})]
        errors+=field_errors
        if errors:
            out[name]=dict(state='FAILED',reason='BINDING_INVALID:'+','.join(errors),**evidence);continue
        if name=='R_APP_MEMORY':
            projected={k:{f:record.get(k,{}).get(f) for f in fields if f in record.get(k,{})} for k in ('features','field_status','field_quality')}
            projected['source_binding']={'binding_valid':True,'same_app_record':True,'app_session_id':record.get('binding',{}).get('app_session_id')}
            cell=original.evaluate(projected)[original.MEMORY_ID]
            state='FAILED' if cell['evaluation_status']!='OK' else 'U' if not cell['available'] else 'T' if cell['value'] else 'F'
            out[name]=dict(cell,state=state,**evidence);continue
        values=[];reason=None
        for field in fields:
            value,error=operand(record,field)
            if error:reason=field+':'+error;break
            values.append(value)
        if reason:out[name]=dict(state='U',reason=reason,**evidence);continue
        if name=='R_NATIVE_BROWSER_MEMORY':
            native,browser=values
            if native<original.MINIMUM_NATIVE_GIB:
                out[name]=dict(state='U',reason='NATIVE_BELOW_0_25_GIB_DOMAIN',**evidence);continue
            try:bound=original.power_two_upper_envelope(native)
            except OverflowError:
                out[name]=dict(state='U',reason='ENVELOPE_OVERFLOW',**evidence);continue
            truth=browser>bound;evidence['upper_envelope_gib']=bound
        elif name in ('R_WEB_MEMORY_DIFFERENCE','D_CPU_DIFFERENCE'):truth=values[0]!=values[1]
        else:truth=values[0]>8
        out[name]=dict(state='T' if truth else 'F',reason='OBSERVED_DEVIATION' if truth else 'OBSERVED_COMPATIBLE',**evidence)
    return out
