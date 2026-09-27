from __future__ import annotations
import io,json,os,sqlite3
from datetime import datetime,timezone
from pathlib import Path
from typing import Literal
import joblib
import pandas as pd
from fastapi import FastAPI,File,HTTPException,UploadFile
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel,Field
from .ml import features_from_readings,score

ROOT=Path(__file__).resolve().parents[1]
MODEL_PATH=Path(os.getenv('METER_MODEL_PATH',ROOT/'models/risk_model.joblib'))
DB_PATH=Path(os.getenv('METER_DB_PATH',ROOT/'data/reviews.sqlite3'))
app=FastAPI(title='Smart Meter Risk API',version='1.0')


def connection():
    DB_PATH.parent.mkdir(parents=True,exist_ok=True)
    c=sqlite3.connect(DB_PATH);c.row_factory=sqlite3.Row
    c.execute('CREATE TABLE IF NOT EXISTS reviews (account_id TEXT PRIMARY KEY, risk_level TEXT NOT NULL, risk_score REAL NOT NULL, status TEXT NOT NULL DEFAULT "New", notes TEXT NOT NULL DEFAULT "", result_json TEXT NOT NULL, analyzed_at TEXT NOT NULL)')
    c.commit();return c


def artifact():
    if not MODEL_PATH.exists():raise HTTPException(503,'Trained model missing. Run python train.py.')
    return joblib.load(MODEL_PATH)


def persist(results):
    now=datetime.now(timezone.utc).isoformat()
    with connection() as c:
        for r in results:
            c.execute('''INSERT INTO reviews (account_id,risk_level,risk_score,status,notes,result_json,analyzed_at)
                VALUES (?,?,?,'New','',?,?) ON CONFLICT(account_id) DO UPDATE SET
                risk_level=excluded.risk_level,risk_score=excluded.risk_score,result_json=excluded.result_json,analyzed_at=excluded.analyzed_at''',
                (r['account_id'],r['risk_level'],r['risk_score'],json.dumps(r),now))
    return now


def analyze(readings):
    try:
        if len(readings)>300000:raise ValueError('Limit: 300,000 readings per analysis.')
        features,quality=features_from_readings(readings)
        if len(features)>3000:raise ValueError('Limit: 3,000 accounts per analysis.')
        scored=score(features,artifact());stamp=persist(scored)
        return {'results':scored,'quality':quality,'analyzed_at':stamp,'model':artifact()['report']['selected_model']}
    except ValueError as exc:raise HTTPException(422,str(exc)) from exc

class ManualInput(BaseModel):
    account_id:str=Field(min_length=1,max_length=100)
    start_timestamp:str
    interval_minutes:int=Field(default=60,ge=15,le=1440)
    kwh_values:list[float]=Field(min_length=72,max_length=5000)

class ReviewInput(BaseModel):
    status:Literal['New','Marked for review','In progress','Closed']
    notes:str=Field(default='',max_length=4000)

@app.get('/api/health')
def health():return {'ok':True,'model_ready':MODEL_PATH.exists()}

@app.get('/api/model')
def model_info():return artifact()['report']

@app.post('/api/analyze/upload')
async def analyze_upload(file:UploadFile=File(...)):
    if not file.filename or not file.filename.lower().endswith('.csv'):raise HTTPException(422,'Upload a CSV file.')
    raw=await file.read(12*1024*1024+1)
    if len(raw)>12*1024*1024:raise HTTPException(413,'CSV is larger than 12 MB.')
    try:df=pd.read_csv(io.BytesIO(raw),dtype={'account_id':'string'},on_bad_lines='error')
    except Exception as exc:raise HTTPException(422,'Could not parse CSV: '+str(exc)) from exc
    return analyze(df)

@app.post('/api/analyze/manual')
def analyze_manual(body:ManualInput):
    try:start=pd.Timestamp(body.start_timestamp)
    except Exception as exc:raise HTTPException(422,'Start timestamp is invalid.') from exc
    if start.tzinfo is None:raise HTTPException(422,'Include a timezone offset in the start timestamp.')
    if any(not 0<=x<1e9 for x in body.kwh_values):raise HTTPException(422,'kWh values must be nonnegative and finite.')
    df=pd.DataFrame({'account_id':[body.account_id.strip()]*len(body.kwh_values),
                     'timestamp':[start+pd.Timedelta(minutes=body.interval_minutes*i) for i in range(len(body.kwh_values))],
                     'kwh':body.kwh_values})
    return analyze(df)

@app.get('/api/reviews')
def reviews(search:str='',risk:str='',status:str=''):
    query='SELECT account_id,risk_level,risk_score,status,notes,result_json,analyzed_at FROM reviews WHERE account_id LIKE ?';params=['%'+search+'%']
    if risk:query+=' AND risk_level=?';params.append(risk)
    if status:query+=' AND status=?';params.append(status)
    query+=' ORDER BY risk_score DESC LIMIT 3000'
    with connection() as c:rows=[dict(r) for r in c.execute(query,params)]
    for row in rows:row['result']=json.loads(row.pop('result_json'))
    return {'items':rows,'count':len(rows)}

@app.patch('/api/reviews/{account_id}')
def update_review(account_id:str,body:ReviewInput):
    with connection() as c:
        cursor=c.execute('UPDATE reviews SET status=?,notes=? WHERE account_id=?',(body.status,body.notes,account_id))
        if not cursor.rowcount:raise HTTPException(404,'Account not found.')
    return {'account_id':account_id,'status':body.status,'notes':body.notes}

@app.get('/api/summary')
def summary():
    with connection() as c:
        total=c.execute('SELECT COUNT(*) FROM reviews').fetchone()[0]
        distribution={row['risk_level']:row['count'] for row in c.execute('SELECT risk_level,COUNT(*) count FROM reviews GROUP BY risk_level')}
        recent=[dict(row) for row in c.execute('SELECT account_id,risk_level,risk_score,status,analyzed_at FROM reviews ORDER BY analyzed_at DESC,risk_score DESC LIMIT 8')]
        queue=c.execute('SELECT COUNT(*) FROM reviews WHERE status IN ("New","Marked for review","In progress") AND risk_level="High Risk"').fetchone()[0]
    return {'accounts':total,'distribution':distribution,'high_risk_open':queue,'recent':recent}

@app.get('/')
def index():return FileResponse(ROOT/'frontend/index.html')
app.mount('/assets',StaticFiles(directory=ROOT/'frontend'),name='assets')
