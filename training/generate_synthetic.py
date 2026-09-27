"""Fabricated smart-meter examples; labels are for engineering tests only."""
import argparse
from pathlib import Path
import numpy as np
import pandas as pd

def main(output):
    rng=np.random.default_rng(26047);readings=[];labels=[]
    for i in range(240):
        # Entire accounts are separated by calendar cohort; later accounts are unseen at training time.
        cohort='earlier' if i<180 else 'later';base_date=pd.Timestamp('2025-01-03T00:00:00Z') if cohort=='earlier' else pd.Timestamp('2025-03-08T00:00:00Z')
        start=base_date+pd.Timedelta(days=(i//3)%18);account=f'MTR-{i+1:05d}'
        label=['Normal Risk','Moderate Risk','High Risk'][i%3];scale=rng.uniform(.4,2.4)
        severity=rng.uniform(.35,.85) if label=='Moderate Risk' else rng.uniform(.08,.55) if label=='High Risk' else rng.uniform(.8,1.18)
        if rng.random()<.12:severity=rng.uniform(.58,1.02) # class overlap to avoid a trivial synthetic benchmark
        for h in range(24*14):
            hour=h%24;weekly=1+.12*np.sin((h//24)/7*2*np.pi);profile=.63 if hour<6 else 1.35 if 18<=hour<=22 else 1
            kwh=max(0,rng.normal(scale*profile*weekly,.25*scale))
            if h>=24*9:kwh*=severity
            if label=='High Risk' and h>=24*9 and rng.random()<.12:kwh=0
            if rng.random()<.015:kwh=0
            readings.append((account,(start+pd.Timedelta(hours=h)).isoformat(),round(kwh,4)))
        labels.append((account,label,cohort))
    output.mkdir(parents=True,exist_ok=True)
    pd.DataFrame(readings,columns=['account_id','timestamp','kwh']).to_csv(output/'synthetic_readings.csv',index=False)
    pd.DataFrame(labels,columns=['account_id','risk_level','cohort']).to_csv(output/'synthetic_labels.csv',index=False)
    pd.DataFrame(readings,columns=['account_id','timestamp','kwh']).query("account_id in ['MTR-00181','MTR-00182','MTR-00183']").to_csv(output/'sample_readings.csv',index=False)
    print('Created 240 synthetic accounts. Labels do not represent verified fraud.')
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',default='data');main(Path(p.parse_args().output))
