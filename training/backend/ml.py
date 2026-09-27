"""Account-level smart meter feature and model pipeline."""
from __future__ import annotations
import json
from datetime import datetime, timezone
from pathlib import Path
import joblib
import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import balanced_accuracy_score, classification_report, confusion_matrix, f1_score, roc_auc_score
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.tree import DecisionTreeClassifier

CLASSES = ['Normal Risk', 'Moderate Risk', 'High Risk']
FEATURES = ['mean_kwh','std_kwh','cv','baseline_kwh','recent_kwh','recent_baseline_ratio','largest_weekly_drop','peak_share','overnight_share','zero_share','longest_zero_run','trend','max_kwh','day_night_ratio']
MIN_READINGS = 72


def clean_readings(df):
    required = {'account_id','timestamp','kwh'}
    missing = required-set(df.columns)
    if missing: raise ValueError('Missing reading columns: '+', '.join(sorted(missing)))
    d=df[['account_id','timestamp','kwh']].copy()
    d['account_id']=d.account_id.astype('string').str.strip()
    d['timestamp']=pd.to_datetime(d.timestamp,errors='coerce',utc=True)
    d['kwh']=pd.to_numeric(d.kwh,errors='coerce')
    invalid=d.account_id.isna()|d.account_id.eq('')|d.timestamp.isna()|d.kwh.isna()|d.kwh.lt(0)|~np.isfinite(d.kwh.fillna(0))
    count=int(invalid.sum());d=d.loc[~invalid]
    duplicates=int(d.duplicated(['account_id','timestamp']).sum())
    d=d.drop_duplicates(['account_id','timestamp'],keep='last').sort_values(['account_id','timestamp'])
    if d.empty: raise ValueError('No valid readings were found.')
    return d, {'invalid_rows':count,'duplicate_timestamps':duplicates}


def features_from_readings(df):
    d,quality=clean_readings(df);out=[]
    for account,g in d.groupby('account_id',sort=False):
        if len(g)<MIN_READINGS: continue
        x=g.kwh.to_numpy(float);n=len(x);quarter=max(1,n//4)
        baseline=x[:-quarter];recent=x[-quarter:];total=max(x.sum(),1e-9)
        hours=g.timestamp.dt.hour.to_numpy();night=x[hours<6].sum();day=x[(hours>=6)&(hours<18)].sum()
        weekly=max(24,n//4);block=[x[i:i+weekly].mean() for i in range(0,n,weekly) if len(x[i:i+weekly])>=24]
        drops=[(a-b)/max(a,.01) for a,b in zip(block,block[1:])]
        longest=run=0
        for val in x:
            run=run+1 if val<.01 else 0;longest=max(longest,run)
        daily=g.assign(day=g.timestamp.dt.floor('D')).groupby('day').kwh.sum()
        out.append({'account_id':str(account),'mean_kwh':x.mean(),'std_kwh':x.std(),'cv':x.std()/max(x.mean(),.01),
            'baseline_kwh':baseline.mean(),'recent_kwh':recent.mean(),'recent_baseline_ratio':recent.mean()/max(baseline.mean(),.01),
            'largest_weekly_drop':max([0]+drops),'peak_share':x[(hours>=18)&(hours<=22)].sum()/total,
            'overnight_share':night/total,'zero_share':np.mean(x<.01),'longest_zero_run':longest,
            'trend':np.polyfit(np.arange(n),x,1)[0],'max_kwh':x.max(),'day_night_ratio':day/max(night,.01),
            'reading_count':n,'first_reading':g.timestamp.iloc[0].isoformat(),'last_reading':g.timestamp.iloc[-1].isoformat(),
            'daily':[[str(k.date()),round(float(v),3)] for k,v in daily.items()]})
    if not out: raise ValueError(f'Each account needs at least {MIN_READINGS} valid readings.')
    f=pd.DataFrame(out).set_index('account_id');return f,quality


def clean_labels(df):
    if not {'account_id','risk_level'}<=set(df): raise ValueError('Labels require account_id and risk_level columns.')
    d=df[['account_id','risk_level']].copy();d.account_id=d.account_id.astype('string').str.strip();d.risk_level=d.risk_level.astype('string').str.strip()
    if d.account_id.isna().any() or d.account_id.eq('').any() or d.account_id.duplicated().any():raise ValueError('Labels need one nonempty row per account.')
    if not d.risk_level.isin(CLASSES).all():raise ValueError('Labels must be Normal Risk, Moderate Risk, or High Risk.')
    return d.set_index('account_id')


def candidates():
    def prep():return ColumnTransformer([('num',Pipeline([('imputer',SimpleImputer(strategy='median')),('scaler',StandardScaler())]),FEATURES)])
    return {'Logistic Regression':Pipeline([('features',prep()),('model',LogisticRegression(max_iter=2000,class_weight='balanced'))]),
            'Decision Tree':Pipeline([('features',prep()),('model',DecisionTreeClassifier(max_depth=7,min_samples_leaf=5,class_weight='balanced',random_state=42))]),
            'Random Forest':Pipeline([('features',prep()),('model',RandomForestClassifier(n_estimators=180,min_samples_leaf=3,class_weight='balanced_subsample',random_state=42,n_jobs=-1))])}


def metrics(model,X,y):
    pred=model.predict(X);prob=model.predict_proba(X);classes=list(model.classes_)
    ordered=np.column_stack([prob[:,classes.index(c)] for c in CLASSES]);y_binary=np.column_stack([(y==c).astype(int) for c in CLASSES])
    try: auc=float(roc_auc_score(y_binary,ordered,average='macro'))
    except ValueError: auc=None
    return {'macro_f1':round(float(f1_score(y,pred,labels=CLASSES,average='macro',zero_division=0)),4),
            'balanced_accuracy':round(float(balanced_accuracy_score(y,pred)),4),
            'roc_auc_ovr_macro':round(auc,4) if auc is not None else None,
            'confusion_matrix':confusion_matrix(y,pred,labels=CLASSES).tolist(),
            'classification_report':classification_report(y,pred,labels=CLASSES,output_dict=True,zero_division=0)}


def train(readings,labels,output_dir,cutoff='2025-03-01T00:00:00Z'):
    f,quality=features_from_readings(readings);joined=f.join(clean_labels(labels),how='inner')
    if len(joined)<90:raise ValueError('Need at least 90 labelled accounts with enough readings.')
    end=pd.to_datetime(joined.last_reading,utc=True);start=pd.to_datetime(joined.first_reading,utc=True);boundary=pd.Timestamp(cutoff)
    train_mask=end<boundary;test_mask=start>=boundary
    # Accounts crossing the cutoff are excluded from both cohorts.
    tr,te=joined[train_mask],joined[test_mask]
    if len(tr)<60 or len(te)<20 or min(tr.risk_level.value_counts().reindex(CLASSES,fill_value=0))<4 or min(te.risk_level.value_counts().reindex(CLASSES,fill_value=0))<2:
        raise ValueError('Need at least 60 earlier and 20 later labelled accounts, with all classes in both cohorts. Change --cutoff to a valid time boundary.')
    Xdev,Xval,ydev,yval=train_test_split(tr[FEATURES],tr.risk_level,test_size=.25,stratify=tr.risk_level,random_state=42)
    comparison={};selection={}
    for name,model in candidates().items():
        model.fit(Xdev,ydev);selection[name]=metrics(model,Xval,yval)
        model.fit(tr[FEATURES],tr.risk_level);comparison[name]={'validation':selection[name],'temporal_test':metrics(model,te[FEATURES],te.risk_level)}
    winner=max(selection,key=lambda name:(selection[name]['macro_f1'],selection[name]['classification_report']['High Risk']['recall']))
    model=candidates()[winner];model.fit(tr[FEATURES],tr.risk_level)
    report={'selected_model':winner,'selection_basis':'Earlier-account validation macro F1; later-period test not used for selection',
      'training_date_utc':datetime.now(timezone.utc).isoformat(),'cutoff_utc':boundary.isoformat(),
      'label_source':'SYNTHETIC development labels' if 'SYNTHETIC' in str(labels.attrs.get('source','')) else 'User supplied; verify provenance',
      'accounts':{'development_train':len(Xdev),'development_validation':len(Xval),'earlier_cohort_total':len(tr),'later_temporal_test':len(te),'excluded_crossing_boundary':len(joined)-len(tr)-len(te)},
      'readings_quality':quality,'classes':CLASSES,'models':comparison}
    dest=Path(output_dir);dest.mkdir(parents=True,exist_ok=True)
    joblib.dump({'pipeline':model,'features':FEATURES,'classes':CLASSES,'report':report},dest/'risk_model.joblib')
    (dest/'evaluation.json').write_text(json.dumps(report,indent=2))
    return report


def explain(f):
    reasons=[]
    if f.recent_baseline_ratio<.7:reasons.append('Sustained usage below historical baseline')
    if f.recent_baseline_ratio>1.6:reasons.append('Recent usage above historical baseline')
    if f.largest_weekly_drop>.35:reasons.append('Sharp change between usage periods')
    if f.zero_share>.12:reasons.append('Frequent near-zero readings')
    if f.longest_zero_run>=8:reasons.append('Extended zero-usage period')
    if f.cv>1.0:reasons.append('High variation in consumption')
    if f.overnight_share>.4:reasons.append('High overnight share')
    return reasons or ['No prominent threshold pattern; review the complete usage trace']


def score(features,artifact):
    model=artifact['pipeline'];p=model.predict_proba(features[FEATURES]);classes=list(model.classes_);result=[]
    for i,(account,f) in enumerate(features.iterrows()):
        probabilities={c:round(float(p[i,classes.index(c)]),5) for c in CLASSES};category=classes[int(np.argmax(p[i]))]
        result.append({'account_id':account,'risk_level':category,'risk_score':round(float(p[i,classes.index('High Risk')]+.5*p[i,classes.index('Moderate Risk')]),5),
                       'class_confidence':probabilities[category],'probabilities':probabilities,'patterns':explain(f),'reading_count':int(f.reading_count),
                       'baseline_kwh':round(float(f.baseline_kwh),3),'recent_kwh':round(float(f.recent_kwh),3),
                       'change_percent':round(float((f.recent_baseline_ratio-1)*100),1),'daily_consumption':f.daily,
                       'first_reading':f.first_reading,'last_reading':f.last_reading})
    return sorted(result,key=lambda x:x['risk_score'],reverse=True)
