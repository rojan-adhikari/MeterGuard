"""Score daily historical consumption using the real-data SGCC model."""
import argparse,json
from pathlib import Path
import joblib
import numpy as np
import pandas as pd
from train_sgcc import extract
p=argparse.ArgumentParser();p.add_argument('--input',required=True,help='CSV with CONS_NO and daily date columns in SGCC format; FLAG optional')
p.add_argument('--model',default='models/sgcc_model.joblib');p.add_argument('--output',default='sgcc_predictions.csv')
a=p.parse_args();df=pd.read_csv(a.input,index_col=False)
if 'CONS_NO' not in df:raise SystemExit('Missing CONS_NO account column')
if 'FLAG' not in df:df.insert(1,'FLAG',0)
artifact=joblib.load(a.model)
X,_,_=extract(df);prob=artifact['pipeline'].predict_proba(X[artifact['features']])[:,1]
out=pd.DataFrame({'account_id':X.index,'theft_label_risk_score':np.round(prob,4),
 'review_priority':np.where(prob>=artifact.get('operating_threshold',.5),'Flag for investigation','Routine review')})
out.to_csv(a.output,index=False)
print(out.to_string(index=False));print('Predictions are not proof of fraud. Verify every flagged account.')
