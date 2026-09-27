import model from './model.json';
export const classes=['Normal Risk','Moderate Risk','High Risk'];
export const minReadings=72;
export type Reading={account_id:string;timestamp:string;kwh:number};
export function parseCsv(input:string):Reading[]{
 const rows:string[][]=[];let row:string[]=[],field='',quote=false;
 for(let i=0;i<input.length;i++){const c=input[i];if(quote){if(c==='"'&&input[i+1]==='"'){field+='"';i++}else if(c==='"')quote=false;else field+=c}else if(c==='"')quote=true;else if(c===','){row.push(field);field=''}else if(c==='\n'||c==='\r'){if(c==='\r'&&input[i+1]==='\n')i++;row.push(field);if(row.some(v=>v.trim()))rows.push(row);row=[];field=''}else field+=c}
 if(quote)throw new Error('Unmatched CSV quote');row.push(field);if(row.some(v=>v.trim()))rows.push(row);
 if(rows.length<2)throw new Error('CSV has no data rows');const keys=rows.shift()!.map(s=>s.replace(/^\uFEFF/,'').trim().toLowerCase());
 for(const key of ['account_id','timestamp','kwh'])if(!keys.includes(key))throw new Error('Missing column: '+key);
 return rows.map(r=>({account_id:r[keys.indexOf('account_id')]??'',timestamp:r[keys.indexOf('timestamp')]??'',kwh:Number(r[keys.indexOf('kwh')])}));
}
const avg=(v:number[])=>v.reduce((a,b)=>a+b,0)/v.length;
function featureOf(account:string,readings:{time:number;kwh:number}[]){
 readings.sort((a,b)=>a.time-b.time);if(readings.length<minReadings)return null;
 const x=readings.map(r=>r.kwh),n=x.length,q=Math.max(1,Math.floor(n/4)),base=avg(x.slice(0,-q)),recent=avg(x.slice(-q)),mean=avg(x),std=Math.sqrt(avg(x.map(v=>(v-mean)**2))),total=Math.max(x.reduce((a,b)=>a+b,0),1e-9);let night=0,day=0,peak=0,run=0,longest=0;
 const daily=new Map<string,number>();for(const r of readings){const d=new Date(r.time),h=d.getUTCHours(),date=d.toISOString().slice(0,10);if(h<6)night+=r.kwh;if(h>=6&&h<18)day+=r.kwh;if(h>=18&&h<=22)peak+=r.kwh;run=r.kwh<.01?run+1:0;longest=Math.max(longest,run);daily.set(date,(daily.get(date)||0)+r.kwh)}
 const weekly=Math.max(24,Math.floor(n/4)),blocks:number[]=[];for(let i=0;i<n;i+=weekly){const v=x.slice(i,i+weekly);if(v.length>=24)blocks.push(avg(v))}let drop=0;for(let i=1;i<blocks.length;i++)drop=Math.max(drop,(blocks[i-1]-blocks[i])/Math.max(blocks[i-1],.01));
 let sx=0,sy=0,sxy=0,sxx=0;for(let i=0;i<n;i++){sx+=i;sy+=x[i];sxy+=i*x[i];sxx+=i*i}const trend=(n*sxy-sx*sy)/(n*sxx-sx*sx);
 const values=[mean,std,std/Math.max(mean,.01),base,recent,recent/Math.max(base,.01),drop,peak/total,night/total,x.filter(v=>v<.01).length/n,longest,trend,x.reduce((a,b)=>Math.max(a,b),0),day/Math.max(night,.01)];
 const normalized=values.map((v,i)=>((Number.isFinite(v)?v:model.impute[i])-model.mean[i])/model.scale[i]);const logits=model.coef.map((co,j)=>model.intercept[j]+co.reduce((sum,c,i)=>sum+c*normalized[i],0));const max=Math.max(...logits),exp=logits.map(v=>Math.exp(v-max)),sum=exp.reduce((a,b)=>a+b,0),prob=exp.map(v=>v/sum);const high=prob[model.classes.indexOf('High Risk')],moderate=prob[model.classes.indexOf('Moderate Risk')],category=model.classes[prob.indexOf(Math.max(...prob))];
 const patterns=[];if(values[5]<.7)patterns.push('Sustained usage below historical baseline');if(values[5]>1.6)patterns.push('Recent usage above historical baseline');if(values[6]>.35)patterns.push('Sharp change between usage periods');if(values[9]>.12)patterns.push('Frequent near-zero readings');if(longest>=8)patterns.push('Extended zero-usage period');if(values[2]>1)patterns.push('High variation in consumption');if(values[8]>.4)patterns.push('High overnight share');
 return {account_id:account,risk_level:category,risk_score:Number((high+.5*moderate).toFixed(5)),class_confidence:Number(prob[model.classes.indexOf(category)].toFixed(5)),probabilities:Object.fromEntries(model.classes.map((c,i)=>[c,Number(prob[i].toFixed(5))])),patterns:patterns.length?patterns:['No prominent threshold pattern; review the complete usage trace'],reading_count:n,baseline_kwh:Number(base.toFixed(3)),recent_kwh:Number(recent.toFixed(3)),change_percent:Number(((recent/Math.max(base,.01)-1)*100).toFixed(1)),daily_consumption:[...daily].map(([d,v])=>[d,Number(v.toFixed(3))]),first_reading:new Date(readings[0].time).toISOString(),last_reading:new Date(readings.at(-1)!.time).toISOString()};
}
export function scoreReadings(input:Reading[]){
 if(input.length>300000)throw new Error('Limit: 300,000 readings per analysis');let invalid=0,duplicates=0;const groups=new Map<string,Map<number,number>>();
 for(const r of input){const id=String(r.account_id??'').trim(),time=Date.parse(String(r.timestamp??'')),v=Number(r.kwh);if(!id||!Number.isFinite(time)||!Number.isFinite(v)||v<0){invalid++;continue}if(!groups.has(id))groups.set(id,new Map());if(groups.get(id)!.has(time))duplicates++;groups.get(id)!.set(time,v)}
 if(groups.size>3000)throw new Error('Limit: 3,000 accounts per analysis');const results=[...groups].map(([id,m])=>featureOf(id,[...m].map(([time,kwh])=>({time,kwh})))).filter((x):x is NonNullable<typeof x>=>x!==null).sort((a,b)=>b.risk_score-a.risk_score);
 if(!results.length)throw new Error('Each account needs at least 72 valid readings');return {results,quality:{invalid_rows:invalid,duplicate_timestamps:duplicates}};
}
