import argparse,json
from pathlib import Path
import pandas as pd
from backend.ml import train
p=argparse.ArgumentParser(description='Train and compare smart meter risk models')
p.add_argument('--readings',default='data/synthetic_readings.csv');p.add_argument('--labels',default='data/synthetic_labels.csv')
p.add_argument('--output',default='models');p.add_argument('--cutoff',default='2025-03-01T00:00:00Z')
a=p.parse_args();readings=pd.read_csv(a.readings);labels=pd.read_csv(a.labels)
if 'synthetic' in Path(a.labels).name.lower():labels.attrs['source']='SYNTHETIC'
report=train(readings,labels,a.output,a.cutoff)
print(json.dumps({'selected_model':report['selected_model'],'accounts':report['accounts'],
 'temporal_test':{k:{'macro_f1':v['temporal_test']['macro_f1'],'balanced_accuracy':v['temporal_test']['balanced_accuracy'],'roc_auc_ovr_macro':v['temporal_test']['roc_auc_ovr_macro']} for k,v in report['models'].items()}},indent=2))
