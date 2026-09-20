from datetime import datetime, timedelta, timezone
from hashlib import sha256
from hmac import compare_digest
from secrets import token_urlsafe, randbelow
from uuid import uuid4
import json
from fastapi import FastAPI, Request, HTTPException, Header, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from workers import asgi, DurableObject, Response
from js import crypto, fetch
from pyodide.ffi import to_js

app=FastAPI(title='AuthentiQ Cloudflare API',version='0.2.0')
app.add_middleware(CORSMiddleware,allow_origins=['*'],allow_credentials=False,allow_methods=['*'],allow_headers=['*'])
def env(r): return r.scope['env']
def now(): return datetime.now(timezone.utc).isoformat()
def norm(v): return v.strip().lower()
def uid(p): return f'{p}_{uuid4().hex[:12]}'
async def phash(v,s=None):
 s=s or token_urlsafe(16)
 key=await crypto.subtle.importKey('raw',to_js(v.encode()),{'name':'PBKDF2'},False,['deriveBits'])
 bits=await crypto.subtle.deriveBits({'name':'PBKDF2','salt':to_js(s.encode()),'iterations':120000,'hash':'SHA-256'},key,256)
 return f'{s}${bytes(bits).hex()}'
async def match(v,h):
 s,e=h.split('$',1); return compare_digest((await phash(v,s)).split('$',1)[1],e)
async def one(r,q,*a): return await env(r).DB.prepare(q).bind(*a).first()
async def many(r,q,*a):
 x=await env(r).DB.prepare(q).bind(*a).all(); return x.get('results',[]) if hasattr(x,'get') else x.results
async def run(r,q,*a): return await env(r).DB.prepare(q).bind(*a).run()
class Signup(BaseModel): name:str=Field(min_length=2); organization:str=Field(min_length=2); email:str; password:str=Field(min_length=8,max_length=128)
class Login(BaseModel): email:str; password:str
class OTP(BaseModel): email:str; otp:str=Field(min_length=6,max_length=6)
class InterviewIn(BaseModel): candidate_name:str=Field(min_length=2); candidate_email:str; title:str=Field(min_length=2); description:str|None=''; scheduled_at:datetime; duration_minutes:int=Field(default=45,ge=15,le=240); monitoring:dict={}
class EventIn(BaseModel): type:str; timestamp:datetime; confidence:float|None=None; severity:str='informational'; metadata:dict={}
class ReviewIn(BaseModel): decision:str=Field(pattern='^(pending|clear|needs_review|escalated)$'); notes:str|None=None
class RoleIn(BaseModel): role:str=Field(pattern='^(admin|interviewer|reviewer)$')
async def current(r,authorization:str|None=Header(default=None)):
 if not authorization or not authorization.lower().startswith('bearer '): raise HTTPException(401,'Authentication required.')
 d=sha256(authorization.split(' ',1)[1].encode()).hexdigest(); x=await one(r,'SELECT s.*,u.name,u.email,u.role FROM sessions s JOIN users u ON u.id=s.user_id WHERE s.token_hash=? AND s.expires_at>?',d,now())
 if not x: raise HTTPException(401,'Your session has expired. Please log in again.')
 return x
async def send_code(r,address,code,purpose):
 key=getattr(env(r),'BREVO_API_KEY',None)
 if not key: raise HTTPException(503,'Transactional email is not configured.')
 response=await fetch('https://api.brevo.com/v3/smtp/email',{'method':'POST','headers':to_js({'accept':'application/json','api-key':key,'content-type':'application/json'},dict_converter='js'),'body':json.dumps({'sender':{'email':getattr(env(r),'BREVO_FROM_EMAIL','ukb.notifications@gmail.com'),'name':'AuthentiQ'},'to':[{'email':address}],'subject':f'Your AuthentiQ {purpose} code','textContent':f'Your AuthentiQ verification code is {code}. It expires in 10 minutes.'})})
 if not response.ok: raise HTTPException(503,'Email provider could not deliver the verification code.')
@app.get('/health')
async def health(): return {'status':'ok','service':'authentiq-api'}
@app.get('/health/ready')
async def ready(r): return {'status':'ready','database':bool(await one(r,'SELECT 1 AS ok'))}
@app.get('/api/v1/status')
async def status(r):
 x=await one(r,'SELECT COUNT(*) AS n FROM organizations'); return {'service':'authentiq','database':'d1','organizations':x.get('n',0) if x else 0}
@app.post('/api/v1/auth/signup/request-otp')
async def signup(r,b:Signup):
 e=norm(b.email)
 if await one(r,'SELECT id FROM users WHERE email=?',e): raise HTTPException(409,'An account with this email already exists.')
 org=uid('org'); u=uid('usr'); code=f'{randbelow(1000000):06d}'
 await run(r,'INSERT INTO organizations(id,name,created_at) VALUES(?,?,?)',org,b.organization,now())
 await run(r,"INSERT INTO users(id,organization_id,email,name,password_hash,verified,role,created_at) VALUES(?,?,?,?,?,0,'admin',?)",u,org,e,b.name,await phash(b.password),now())
 await run(r,'INSERT OR REPLACE INTO otp_codes VALUES(?,?,?,?,0)',e,await phash(code),'signup',(datetime.now(timezone.utc)+timedelta(minutes=10)).isoformat()); await send_code(r,e,code,'signup')
 return {'status':'otp_sent','message':'A verification code has been sent to your email.'}
@app.post('/api/v1/auth/signup/verify')
async def signup_verify(r,b:OTP):
 e=norm(b.email); x=await one(r,"SELECT * FROM otp_codes WHERE email=? AND purpose='signup'",e)
 if not x or x['expires_at']<now() or x['attempts']>=5 or not await match(b.otp,x['code_hash']): raise HTTPException(400,'This verification code is invalid or expired.')
 await run(r,'UPDATE users SET verified=1 WHERE email=?',e); await run(r,'DELETE FROM otp_codes WHERE email=?',e); return {'status':'verified','message':'Your AuthentiQ account is verified.'}
@app.post('/api/v1/auth/login/request-otp')
async def login(r,b:Login):
 e=norm(b.email); u=await one(r,'SELECT * FROM users WHERE email=?',e)
 if not u or not await match(b.password,u['password_hash']): raise HTTPException(401,'Email or password is incorrect.')
 if not u['verified']: raise HTTPException(403,'Please verify your email before logging in.')
 code=f'{randbelow(1000000):06d}'; await run(r,'INSERT OR REPLACE INTO otp_codes VALUES(?,?,?,?,0)',e,await phash(code),'login',(datetime.now(timezone.utc)+timedelta(minutes=10)).isoformat()); await send_code(r,e,code,'login'); return {'status':'otp_sent','message':'A login code has been sent to your email.'}
@app.post('/api/v1/auth/login/verify')
async def login_verify(r,b:OTP):
 e=norm(b.email); x=await one(r,"SELECT * FROM otp_codes WHERE email=? AND purpose='login'",e); u=await one(r,'SELECT * FROM users WHERE email=?',e)
 if not x or not u or x['expires_at']<now() or x['attempts']>=5 or not await match(b.otp,x['code_hash']): raise HTTPException(400,'This login code is invalid or expired.')
 raw=token_urlsafe(48); await run(r,'INSERT INTO sessions VALUES(?,?,?,?,?)',sha256(raw.encode()).hexdigest(),u['id'],u['organization_id'],(datetime.now(timezone.utc)+timedelta(days=7)).isoformat(),now()); await run(r,'DELETE FROM otp_codes WHERE email=?',e); return {'status':'authenticated','session_token':raw,'user_id':u['id'],'organization_id':u['organization_id']}
@app.post('/api/v1/auth/logout')
async def logout(r,authorization:str|None=Header(default=None)):
 if authorization and authorization.lower().startswith('bearer '): await run(r,'DELETE FROM sessions WHERE token_hash=?',sha256(authorization.split(' ',1)[1].encode()).hexdigest())
 return {'status':'logged_out'}
@app.get('/api/v1/auth/me')
async def me(s=Depends(current)): return {k:s[k] for k in ('user_id','organization_id','role','name','email')}
def iv(x): x['monitoring']=json.loads(x.get('monitoring_json') or '{}'); return x
@app.post('/api/v1/interviews',status_code=201)
async def create(r,b:InterviewIn,s=Depends(current)):
 i=uid('int'); t=token_urlsafe(32); room='room_'+i; z=now(); await run(r,'INSERT INTO interviews VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)',i,s['organization_id'],b.candidate_name,norm(b.candidate_email),b.title,b.description or '',b.scheduled_at.isoformat(),b.duration_minutes,'scheduled',json.dumps(b.monitoring),t,room,z); return {'id':i,'organization_id':s['organization_id'],**b.model_dump(mode='json'),'status':'scheduled','invitation_token':t,'room_name':room,'created_at':z}
@app.get('/api/v1/interviews')
async def interviews(r,s=Depends(current)): return [iv(x) for x in await many(r,'SELECT * FROM interviews WHERE organization_id=? ORDER BY scheduled_at',s['organization_id'])]
@app.get('/api/v1/candidates')
async def candidates(r,s=Depends(current)):
 out={}
 for x in await many(r,'SELECT * FROM interviews WHERE organization_id=? ORDER BY created_at DESC',s['organization_id']):
  c=out.setdefault(x['candidate_email'],{'email':x['candidate_email'],'name':x['candidate_name'],'interviews':0,'latest_status':x['status'],'latest_interview_id':x['id']}); c['interviews']+=1
 return list(out.values())
@app.get('/api/v1/interviews/{i}')
async def interview(r,i,s=Depends(current)):
 x=await one(r,'SELECT * FROM interviews WHERE id=? AND organization_id=?',i,s['organization_id'])
 if not x: raise HTTPException(404,'Interview not found')
 x=iv(x); x['events']=await many(r,'SELECT * FROM integrity_events WHERE interview_id=? ORDER BY timestamp',i); return x
@app.post('/api/v1/interviews/{i}/events',status_code=201)
async def event(r,i,b:EventIn,s=Depends(current)):
 if not await one(r,'SELECT id FROM interviews WHERE id=? AND organization_id=?',i,s['organization_id']): raise HTTPException(404,'Interview not found')
 e=uid('evt'); z=now(); await run(r,'INSERT INTO integrity_events VALUES(?,?,?,?,?,?,?,?)',e,i,b.type,b.timestamp.isoformat(),b.confidence,b.severity,json.dumps(b.metadata),z); return {'id':e,'interview_id':i,**b.model_dump(mode='json'),'created_at':z}
@app.get('/api/v1/invitations/{t}')
async def invite(r,t):
 x=await one(r,'SELECT * FROM interviews WHERE invitation_token=?',t)
 if not x: raise HTTPException(404,'Invitation not found or expired.')
 return {'interview_id':x['id'],'candidate_name':x['candidate_name'],'title':x['title'],'scheduled_at':x['scheduled_at'],'duration_minutes':x['duration_minutes'],'room_name':x['room_name'],'status':x['status']}
@app.post('/api/v1/invitations/{t}/accept')
async def accept(r,t):
 x=await one(r,'SELECT * FROM interviews WHERE invitation_token=?',t)
 if not x: raise HTTPException(404,'Invitation not found or expired.')
 return {'status':'accepted','interview_id':x['id'],'room_name':x['room_name']}
@app.get('/api/v1/interviews/{i}/report')
async def report(r,i,s=Depends(current)):
 x=await one(r,'SELECT * FROM interviews WHERE id=? AND organization_id=?',i,s['organization_id']); rows=await many(r,'SELECT * FROM integrity_events WHERE interview_id=? ORDER BY timestamp',i)
 if not x: raise HTTPException(404,'Interview not found')
 c={'informational':0,'warning':0,'critical':0}
 for e in rows:c[e['severity']]=c.get(e['severity'],0)+1
 return {'interview_id':i,'candidate_name':x['candidate_name'],'title':x['title'],'status':x['status'],'summary':{'total_events':len(rows),'severity_counts':c,'human_review_required':c.get('critical',0)>0 or c.get('warning',0)>0},'timeline':rows}
@app.put('/api/v1/interviews/{i}/review')
async def review(r,i,b:ReviewIn,s=Depends(current)):
 if not await one(r,'SELECT id FROM interviews WHERE id=? AND organization_id=?',i,s['organization_id']): raise HTTPException(404,'Interview not found')
 z=now(); rid=uid('rev'); await run(r,'INSERT INTO reviews VALUES(?,?,?,?,?,?,?) ON CONFLICT(interview_id) DO UPDATE SET decision=excluded.decision,notes=excluded.notes,updated_at=excluded.updated_at',rid,i,s['user_id'],b.decision,b.notes or '',z,z); return await one(r,'SELECT * FROM reviews WHERE interview_id=?',i)
@app.get('/api/v1/reviews')
async def reviews(r,s=Depends(current)): return await many(r,'SELECT r.*,i.candidate_name,i.title FROM reviews r JOIN interviews i ON i.id=r.interview_id WHERE i.organization_id=?',s['organization_id'])
@app.get('/api/v1/organization/members')
async def members(r,s=Depends(current)): return await many(r,'SELECT id,name,email,role,verified FROM users WHERE organization_id=? ORDER BY created_at',s['organization_id'])
@app.patch('/api/v1/organization/members/{u}/role')
async def member_role(r,u,b:RoleIn,s=Depends(current)):
 if s['role']!='admin': raise HTTPException(403,'Only organization admins can change roles.')
 await run(r,'UPDATE users SET role=? WHERE id=? AND organization_id=?',b.role,u,s['organization_id']); return {'id':u,'role':b.role}
class InterviewRoom(DurableObject):
 async def fetch(self,request): return Response.json({'status':'room-online'})
Default=asgi.entrypoint(app)
