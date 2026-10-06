"""Publication candidate SVG/PNG and exact CSV data, from saved tables only."""
import argparse,csv,os
from closeout_io import *
os.environ.setdefault('MPLCONFIGDIR',str(HERE/'.mplconfig'))
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

VIEWS=['V_APP','V_BROWSER','V_BOTH','V_BOTH_REL']
NAMES=['App view','Browser view','Both','Both + C1/C2']
COLORS=['#0072B2','#E69F00','#009E73','#CC79A7']
plt.rcParams.update({'font.family':'DejaVu Sans','font.size':10,'axes.spines.top':False,'axes.spines.right':False,'svg.fonttype':'none','svg.hashsalt':'b3b-fixed-evidence-v1','savefig.dpi':220})

def plot(table_dir,output):
    tables=Path(table_dir);out=Path(output);out.mkdir(parents=True,exist_ok=True)
    main=read(tables/'four_view.json');lookup={(r['plan'],r['view']):r for r in main}
    manifest=[]
    def save(fig,name,records,caption):
        fig.savefig(out/(name+'.svg'),metadata={'Date':None});fig.savefig(out/(name+'.png'),metadata={'Software':'B3-B saved-only plotting'})
        csv_write(out/(name+'.csv'),records);plt.close(fig)
        manifest.append(dict(figure=name,svg=name+'.svg',png=name+'.png',csv=name+'.csv',caption=caption,model_calls=0))
    def bars(ax,plan,metric,scope='all'):
        vals=[];counts_=[]
        for view in VIEWS:
            r=lookup[plan,view]
            if scope=='all':a,n=r[metric+'_T'],r[metric+'_n']
            else:a=sum(r[f'{scope}_{f}_T'] for f in ('language','timezone'));n=sum(r[f'{scope}_{f}_n'] for f in ('language','timezone'))
            vals.append(100*a/n if n else 0);counts_.append((a,n))
        ax.bar(range(4),vals,color=COLORS,width=.65)
        for i,(a,n) in enumerate(counts_):ax.text(i,vals[i]+2,f'{a}/{n}',ha='center',va='bottom',fontsize=11)
        ax.set_xticks(range(4),NAMES,rotation=18,ha='right');ax.set_ylim(0,118);ax.set_yticks([0,25,50,75,100]);ax.set_ylabel('Triggered (%)' if metric=='attack' else 'Normal alarms (%)');ax.grid(axis='y',alpha=.2);ax.set_axisbelow(True)
    fig=plt.figure(figsize=(14,8.6),layout='constrained');gs=fig.add_gridspec(2,6)
    for i,plan in enumerate(('P0','P1','P2')):
        ax=fig.add_subplot(gs[0,i*2:(i+1)*2]);bars(ax,plan,'attack');ax.set_title({'P0':'P0: development fit (n=14)','P1':'P1: pilot batch held out (n=6)','P2':'P2: matched batch held out (n=8)'}[plan],fontsize=11)
    ax=fig.add_subplot(gs[1,:3]);bars(ax,'P2','attack','App');ax.set_title('P2 App interventions (n=4): endpoint/configuration unseen in training')
    ax=fig.add_subplot(gs[1,3:]);bars(ax,'P2','attack','Browser');ax.set_title('P2 Browser interventions (n=4): direction represented in training')
    fig.suptitle('Fixed language/timezone views: intervention triggers',fontsize=16)
    save(fig,'fig01_four_view_detection',main,'Counts accompany rates. P0 is in-sample development; P1/P2 are historically exposed whole-batch development holdouts. Weighted scores are not calibrated attack probabilities.')
    fig,axs=plt.subplots(1,3,figsize=(14,4.6),layout='constrained')
    for ax,plan,n in zip(axs,('P0','P1','P2'),(46,12,34)):
        bars(ax,plan,'normal');ax.set_title(f'{plan}: normal denominator n={n}')
    fig.suptitle('Normal alarms in the same primary comparison cohorts',fontsize=16)
    save(fig,'fig02_four_view_normal_alarms',main,'Normal denominators differ: P0 46, P1 12, P2 34. Failures remain visible; all primary tree U/FAILED counts are 0, not proof of complete input coverage.')
    metrics=read(tables/'metric_index.json');mtc=[r for r in metrics if r['model_family']=='B2C_incremental_rule' and r['cohort'].startswith('mtc_') and r['group']=='NORMAL']
    fig,axs=plt.subplots(1,3,figsize=(17,7),layout='constrained')
    state_colors={'T':'#D55E00','F':'#56B4E9','U':'#E69F00','FAILED':'#444444'}
    short={'R_FULL':'Full','R_NO_CROSS':'No cross','R_NO_MATCHED_NORMAL_CAP':'No matched cap'}
    for ax,co,n in zip(axs,('mtc_discovery','mtc_development','mtc_reserved_validation'),(630,144,117)):
        rr=sorted([r for r in mtc if r['cohort']==co],key=lambda r:(r['base_config'],SETTINGS_NAMES.index(r['setting'])))
        left=np.zeros(len(rr))
        for state in STATES:
            values=np.array([r[state]/n*100 for r in rr]);ax.barh(range(len(rr)),values,left=left,color=state_colors[state],label=state,height=.65);left+=values
        labels=[f"Base {r['base_config']:02d} / {short[r['setting']]}" for r in rr]
        ax.set_yticks(range(len(rr)),labels,fontsize=9);ax.invert_yaxis();ax.set_xlim(0,132);ax.set_xticks([0,25,50,75,100]);ax.set_xlabel('Fraction of fixed normal members (%)');ax.set_title(f'{co.replace("mtc_","")} (n={n})',pad=28)
        for i,r in enumerate(rr):ax.text(101,i,f"{r['T']}/{r['F']}/{r['U']}/{r['FAILED']}",va='center',fontsize=8)
        ax.text(101,-.8,'T / F / U / FAILED',fontsize=8)
    handles,labels=axs[0].get_legend_handles_labels();fig.legend(handles,labels,loc='outside lower center',ncol=4)
    fig.suptitle('Frozen rule method and two minimal incremental-module ablations',fontsize=16)
    save(fig,'fig03_rule_mtc_states',compact_for_csv(mtc),'Three base configurations are shown separately; they do not triple the number of independent MTC members. Tree binary coverage is a different quantity; 33/951 dual-endpoint inputs are partial.')
    examples=read(tables/'preference_examples.json');groups={}
    for r in examples:
        key=(r['cohort'],r['identity'],r['browser_language'],r['browser_language_count'],*[r[p+'_'+v] for p in ('P0','P1','P2') for v in ('V_BOTH','V_BOTH_REL')])
        groups.setdefault(key,[]).append(r)
    display=[]
    for key,rs in sorted(groups.items(),key=lambda kv:(kv[0][1]!='NORMAL',kv[0][0])):
        r=rs[0];name=('Matched normal preference' if r['identity']=='NORMAL' else 'Matched script language' if r['cohort']=='b2b42' else 'Pilot script language')
        display.append([name+f' (n={len(rs)})',r['app_language'],r['browser_language'],r['browser_first_language'],str(r['browser_language_count']),r['C2'],*[r[p+'_V_BOTH']+' / '+r[p+'_V_BOTH_REL'] for p in ('P0','P1','P2')]])
    fig,ax=plt.subplots(figsize=(16,4.4),layout='constrained');ax.axis('off')
    labels=['Observed group','App language','Browser language','Browser first','List length','C2','P0 Both / Rel','P1 Both / Rel','P2 Both / Rel']
    t=ax.table(cellText=display,colLabels=labels,loc='center',cellLoc='center',colWidths=[.23,.10,.11,.10,.07,.04,.085,.085,.085])
    t.auto_set_font_size(False);t.set_fontsize(10);t.scale(1,2.5)
    for (row,col),cell in t.get_celld().items():
        cell.set_edgecolor('#d0d0d0')
        if row==0:cell.set_facecolor('#e7eef3');cell.set_text_props(weight='bold')
        elif col in (4,6):cell.set_facecolor('#fff2cf')
    ax.set_title('Preferred-tag disagreement is shared; observed list lengths differ',fontsize=16,pad=15)
    fig.text(.5,.05,'P0 REL uses Browser list length <= 2.5. This is recipe dependence, not identification of arbitrary manipulation intent.\nT = alert, F = no alert. These exposed samples retain their plan-specific training/holdout roles.',ha='center',fontsize=10)
    save(fig,'fig04_preference_recipe',examples,'C2 sees preferred-tag mismatch in both normal preferences and scripts. Their full raw inputs are not identical; list length differs. Every repeat and all plan-specific scores remain in CSV.')
    write(out/'FIGURES.json',manifest)
    print('Saved-only figures:',len(manifest),'SVG/PNG/CSV each')

def compact_for_csv(records):return [{k:v for k,v in r.items() if k!='sample_ids'} for r in records]
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--tables',type=Path,default=HERE/'tables');p.add_argument('--output',type=Path,default=HERE/'figures');args=p.parse_args();plot(args.tables,args.output)
