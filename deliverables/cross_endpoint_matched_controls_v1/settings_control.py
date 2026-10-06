"""Real Android / Chrome preference changes. No CDP, JS, or payload editing."""
import datetime, json, sys, time
from pathlib import Path
import ui
def snapshot():
    return {k:ui.adb('shell',*cmd) for k,cmd in {
        'locale':['getprop','persist.sys.locale'],'configuration':['cmd','activity','get-config'],
        'timezone':['getprop','persist.sys.timezone'],'auto_time_zone':['settings','get','global','auto_time_zone'],
        'device_clock':['date','+%s,%z,%Z'],'system_locales':['settings','get','system','system_locales']}.items()}
def texts(r):return [n.get('text') for n in r.iter('node') if n.get('text')]
def browser_languages():
    ui.adb('shell','am','force-stop','com.android.chrome')
    ui.adb('shell','am','start','-W','-a','android.intent.action.VIEW','-d','about:blank','-p','com.android.chrome')
    for _ in range(5):
        current=ui.dump()
        if 'Chrome notifications make things easier' in texts(current):ui.tap('No thanks');continue
        if any(n.get('resource-id')=='com.android.chrome:id/menu_button' for n in current.iter('node')):break
    ui.tap_id('com.android.chrome:id/menu_button');ui.tap('Settings')
    for _ in range(4):
        if 'Languages' in texts(ui.dump()):break
        ui.adb('shell','input','swipe','600','2080','600','680','450')
    ui.tap('Languages')
    return ui.dump()
def preference_list(r):
    return [n.get('text') for n in r.iter('node') if n.get('resource-id')=='com.android.chrome:id/title']
def system_language(action):
    ui.adb('shell','am','start','-W','-a','android.settings.LOCALE_SETTINGS')
    before=ui.dump()
    if action=='apply':
        ui.tap('Add a language');ui.tap('Search');ui.adb('shell','input','text','French')
        ui.tap('Français');ui.tap('France')
        ui.tap('Edit system language list, Français (France)');ui.tap('Move up');ui.tap('Change')
    else:
        french=ui.adb('shell','getprop','persist.sys.locale').startswith('fr')
        if 'Français (France)' in texts(before):
            ui.tap(('Modifier la liste des langues du système, ' if french else 'Edit system language list, ')+'Français (France)')
            ui.tap('Supprimer' if french else 'Remove')
            if french:ui.tap('Modifier')
    after=ui.dump()
    return {'before_ui_text':texts(before),'after_ui_text':texts(after)}
def browser_language(action):
    before=browser_languages();prefs=preference_list(before)
    if action=='apply':
        if prefs!=['English (United States)','English']:raise ValueError('UNEXPECTED_BROWSER_BASELINE:'+repr(prefs))
        ui.tap('Add language');ui.tap('Search');ui.adb('shell','input','text','French')
        ui.tap('French (France)');ui.tap('French (France) Options');ui.tap('Move to top')
    elif 'French (France)' in prefs:
        ui.tap('French (France) Options');ui.tap('Remove')
    after=ui.dump();actual=preference_list(after)
    expected=['French (France)','English (United States)','English'] if action=='apply' else ['English (United States)','English']
    if actual!=expected:raise ValueError('BROWSER_PREFERENCE_ORDER_MISMATCH:'+repr(actual))
    # Engineering correction: immediate force-stop lost the observed UI preference.
    # Fixed once from a persistence-only diagnostic, before any model evaluation.
    time.sleep(15)
    durable=preference_list(browser_languages())
    if durable!=expected:raise ValueError('BROWSER_PREFERENCE_NOT_DURABLE:'+repr(durable))
    return {'before_preferred_languages':prefs,'after_preferred_languages':actual,'after_ui_text':texts(after),
            'persistence_wait_seconds':15,'after_cold_restart_preferred_languages':durable,'durability_verified':True}
def execute(scenario,action,out):
    ui.OUT=out/'settings_ui';r={'scenario':scenario,'action':action,'started_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'path':'real_settings_ui_or_android_alarm_service','status':'NOT_NEEDED'}
    r['before']=snapshot()
    try:
        if action!='snapshot' and scenario.startswith('L_'):
            if scenario=='L_SYS_LANG':r['operation']=system_language(action)
            elif scenario=='L_BROWSER_LANG':r['operation']=browser_language(action)
            elif scenario=='L_SYS_TZ':
                ui.adb('shell','settings','put','global','auto_time_zone','0')
                ui.adb('shell','cmd','alarm','set-timezone','Asia/Tokyo' if action=='apply' else 'Asia/Shanghai')
                if action=='restore':ui.adb('shell','settings','put','global','auto_time_zone','1')
            r['status']='EXECUTED'
        r['after']=snapshot()
        if action!='snapshot' and scenario=='L_SYS_LANG':
            if r['after']['locale']!=('fr-FR' if action=='apply' else 'en-US'):raise ValueError('SYSTEM_LOCALE_MISMATCH')
        if action!='snapshot' and scenario=='L_SYS_TZ':
            if r['after']['timezone']!=('Asia/Tokyo' if action=='apply' else 'Asia/Shanghai'):raise ValueError('SYSTEM_ZONE_MISMATCH')
    except Exception as e:
        r['status']='FAILED';r['error']=repr(e);r['after']=snapshot()
    r['finished_at']=datetime.datetime.now(datetime.timezone.utc).isoformat()
    with (out/'settings_operations.jsonl').open('a') as f:f.write(json.dumps(r,ensure_ascii=False)+'\n')
    return r
if __name__=='__main__':print(json.dumps(execute(sys.argv[1],sys.argv[2],Path(sys.argv[3]).resolve()),ensure_ascii=False))
