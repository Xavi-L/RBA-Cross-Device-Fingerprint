"""Explicit v16 twelve-position profile; the v15 entry remains fixed."""
import importlib.util
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[2]
HERE=Path(__file__).resolve().parent
if str(ROOT) not in sys.path:sys.path.insert(0,str(ROOT))
from hybridguard_agent.research import screen_geometry_io as evidence


def load(name):
    spec=importlib.util.spec_from_file_location('geometry_closeout_'+name,ROOT/'deliverables/screen_geometry_observation_v1'/f'{name}.py')
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module


def validate(s):
    try:
        if (s['experiment_id']!='screen-geometry-v16-closeout-v1' or s['model_fit_calls']!=0 or s['planned_records']!=12
                or s['collector']['version_code']!=16 or s['collector']['version_name']!='1.6.9-expanded-v2.2-geometry'
                or s['module_version']!='featureapp-geometry-v1.1' or s['attempts_per_position']!=1
                or s['context_prefix']!='screen-geometry-v16:' or s['identity_prefix']!='screen-geometry-v16-'):
            raise ValueError('V16_CLOSEOUT_IDENTITY_REQUIRED')
        envs=['api29_swiftshader','api30_swiftshader','api36_swiftshader']
        if [e['environment_group_id'] for e in s['environments']]!=envs:raise ValueError('FIXED_ENVIRONMENTS_REQUIRED')
        wanted=[]
        for env in envs:
            wanted += [dict(environment=env,step_id='v16-A-'+p,process_type='A',round=1,phase=p,control='cdp') for p in ('clean_pre','change','clean_post')]
            if env==envs[0]:wanted += [dict(environment=env,step_id='v16-'+k,process_type=k,round=1,phase='standalone',control=c,standalone=True)
                for k,c in (('DEFAULT','default'),('DEGRADE','fault'),('POST_FAULT','default'))]
        if s['positions']!=wanted:raise ValueError('FIXED_TWELVE_POSITIONS_REQUIRED')
        params={'width':393,'height':851,'deviceScaleFactor':2.75,'mobile':True,'screenWidth':393,'screenHeight':851,'positionX':0,'positionY':0}
        if s['screen_configuration']['cdpEmulation']['applyCommands']!=[{'method':'Emulation.setDeviceMetricsOverride','params':params}]:raise ValueError('ORIGINAL_SCREEN_PARAMETERS_REQUIRED')
    except (KeyError,TypeError,ValueError) as error:raise evidence.EvidenceError(str(error)) from error
    return s
