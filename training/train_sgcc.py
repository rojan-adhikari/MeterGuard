"""Train a binary risk classifier on the public SGCC historical daily dataset.

This dataset's FLAG is a published label, not direct evidence for any new account.
No account appears in more than one split.
"""
import argparse,json
from datetime import datetime,timezone
from pathlib import Path
import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.tree import DecisionTreeClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.impute import SimpleImputer
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import precision_recall_fscore_support, confusion_matrix, average_precision_score, roc_auc_score, balanced_accuracy_score
from sklearn.model_selection import train_test_split

FEATURES=['mean_kwh','median_kwh','std_kwh','cv','q10_kwh','q90_kwh','max_kwh','zero_share','missing_share','first_180_mean','last_180_mean','recent_baseline_ratio','recent_30_mean','previous_180_mean','recent_30_ratio','monthly_variation','weekday_weekend_ratio','max_zero_run','negative_value_share']

def extract(frame):
    date_cols=sorted([c for c in frame if c not in ('CONS_NO','FLAG')],key=lambda x:pd.Timestamp(x))
    x=frame[date_cols].apply(pd.to_numeric,errors='coerce').to_numpy(dtype=np.float32)
    neg=np.nanmean(x<0,axis=1);x[x<0]=np.nan
    with np.errstate(invalid='ignore',divide='ignore'):
        mean=np.nanmean(x,axis=1);median=np.nanmedian(x,axis=1);std=np.nanstd(x,axis=1)
        q10=np.nanpercentile(x,10,axis=1);q90=np.nanpercentile(x,90,axis=1);maximum=np.nanmax(x,axis=1)
        zero=np.nansum(x<.01,axis=1)/np.maximum(np.sum(np.isfinite(x),axis=1),1)
        first=np.nanmean(x[:,:180],axis=1);last=np.nanmean(x[:,-180:],axis=1)
        recent=np.nanmean(x[:,-30:],axis=1);prev=np.nanmean(x[:,-210:-30],axis=1)
        monthmeans=np.stack([np.nanmean(x[:,i:i+30],axis=1) for i in range(0,x.shape[1],30)],axis=1)
        monthvar=np.nanstd(monthmeans,axis=1)/np.maximum(np.nanmean(monthmeans,axis=1),.01)
        weekend=np.array([pd.Timestamp(d).dayofweek>=5 for d in date_cols]);weekday_mean=np.nanmean(x[:,~weekend],axis=1);weekend_mean=np.nanmean(x[:,weekend],axis=1)
        missing=np.mean(~np.isfinite(x),axis=1)
    runs=np.zeros(len(x),dtype=np.int16);longest=runs.copy()
    for col in range(x.shape[1]):
        runs=np.where(np.isfinite(x[:,col])&(x[:,col]<.01),runs+1,0);longest=np.maximum(longest,runs)
    values=np.column_stack([mean,median,std,std/np.maximum(mean,.01),q10,q90,maximum,zero,missing,first,last,last/np.maximum(first,.01),recent,prev,recent/np.maximum(prev,.01),monthvar,weekday_mean/np.maximum(weekend_mean,.01),longest,neg]).astype(np.float32)
    values[~np.isfinite(values)]=np.nan
    return pd.DataFrame(values,columns=FEATURES,index=frame.CONS_NO.astype(str)),frame.FLAG.astype(int).to_numpy(),date_cols

def measure(model,X,y):
    p=model.predict_proba(X)[:,1];pred=(p>=.5).astype(int)
    pr,re,f1,_=precision_recall_fscore_support(y,pred,average='binary',zero_division=0)
    return {'precision':round(float(pr),4),'recall':round(float(re),4),'f1':round(float(f1),4),
      'balanced_accuracy':round(float(balanced_accuracy_score(y,pred)),4),'average_precision':round(float(average_precision_score(y,p)),4),
      'roc_auc':round(float(roc_auc_score(y,p)),4),'confusion_matrix':confusion_matrix(y,pred,labels=[0,1]).tolist()}

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--input',required=True);parser.add_argument('--output',default='models');a=parser.parse_args()
    df=pd.read_csv(a.input,index_col=False);assert df.CONS_NO.is_unique and set(df.FLAG)=={0,1}
    X,y,dates=extract(df);ix=np.arange(len(X));dev,test=train_test_split(ix,test_size=.2,stratify=y,random_state=42);train,val=train_test_split(dev,test_size=.25,stratify=y[dev],random_state=42)
    def candidates():return {
      'Logistic Regression':Pipeline([('imputer',SimpleImputer(strategy='median',add_indicator=True)),('scaler',StandardScaler()),('model',LogisticRegression(class_weight='balanced',max_iter=1500))]),
      'Decision Tree':Pipeline([('imputer',SimpleImputer(strategy='median',add_indicator=True)),('model',DecisionTreeClassifier(max_depth=8,min_samples_leaf=30,class_weight='balanced',random_state=42))]),
      'Random Forest':Pipeline([('imputer',SimpleImputer(strategy='median',add_indicator=True)),('model',RandomForestClassifier(n_estimators=120,min_samples_leaf=8,max_features='sqrt',class_weight='balanced_subsample',n_jobs=-1,random_state=42))])}
    selection={};models=candidates()
    for name,model in models.items():
        model.fit(X.iloc[train],y[train]);selection[name]=measure(model,X.iloc[val],y[val]);print(name,selection[name],flush=True)
    winner=max(selection,key=lambda name:selection[name]['average_precision'])
    final=candidates()[winner];final.fit(X.iloc[dev],y[dev]);test_metrics=measure(final,X.iloc[test],y[test])
    report={'dataset':'SGCC Electricity Theft Detection public historical dataset','source':'https://github.com/henryRDlab/ElectricityTheftDetection',
       'training_date_utc':datetime.now(timezone.utc).isoformat(),'records':len(df),'positive_labels':int(y.sum()),'date_range':[str(pd.Timestamp(dates[0]).date()),str(pd.Timestamp(dates[-1]).date())],
       'split':{'training_accounts':len(train),'validation_accounts':len(val),'test_accounts':len(test),'rule':'disjoint stratified accounts; test accounts untouched until model selection'},
       'selected_model':winner,'selection_metric':'validation average precision','validation':selection,'test':test_metrics,'threshold':.5,
       'limits':'Daily historical consumption and published account labels. No confirmed theft period or field evidence for new cases; not a fraud verdict.'}
    dest=Path(a.output);dest.mkdir(exist_ok=True,parents=True)
    joblib.dump({'pipeline':final,'features':FEATURES,'report':report},dest/'sgcc_model.joblib')
    (dest/'sgcc_evaluation.json').write_text(json.dumps(report,indent=2))
    print('SELECTED',winner,'TEST',test_metrics,flush=True)
if __name__=='__main__':main()
