"""Hearth: dependency-free local property management server.

Run python server.py. The loopback-only server is intentionally not an internet
deployment. The database, domain operations and UI are separated for migration.
"""
from __future__ import annotations
import argparse
import base64
import calendar
import csv
import hashlib
import html
import io
import json
import mimetypes
import os
from pathlib import Path
import secrets
import sqlite3
import sys
import threading
import uuid
import zipfile
import transfers
from email_service import GoogleWorkspaceEmail
from receipt_pdf import create_receipt_pdf
from contextlib import contextmanager, closing
from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit, parse_qs, quote

ROOT = Path(__file__).resolve().parent
KINDS = ('properties','units','tenants','leases','charges','payments','expenses','work','vendors','inspections','applications','listings','tasks','fields','categories')
LABELS = dict(properties='Property', units='Unit', tenants='Tenant', leases='Lease', charges='Charge', payments='Payment', expenses='Expense', work='Work order', vendors='Vendor', inspections='Inspection', applications='Application', listings='Listing', tasks='Task', fields='Custom field', categories='Category')
MONEY_FIELDS = {'properties':['market_rent','deposit'], 'units':['market_rent','deposit'], 'leases':['rent','deposit','late_fee'], 'charges':['amount'], 'payments':['amount'], 'expenses':['amount'], 'work':['estimate'], 'listings':['rent','deposit']}
REQUIRED = {'properties':['name','address'], 'units':['name','property_id'], 'tenants':['name'], 'leases':['name','property_id','tenant_id','start','rent'], 'charges':['tenant_id','property_id','date','amount','category'], 'payments':['tenant_id','property_id','date','amount','category'], 'expenses':['date','amount','category','description'], 'work':['title','property_id','category','status'], 'vendors':['name'], 'inspections':['title','property_id','date'], 'applications':['name','property_id','status'], 'listings':['title','property_id','rent'], 'tasks':['title','date'], 'fields':['name','entity','field_type'], 'categories':['name','scope']}
REFERENCES = {'property_id':'properties','unit_id':'units','tenant_id':'tenants','lease_id':'leases','charge_id':'charges','work_id':'work','vendor_id':'vendors'}
STATUS_OPTIONS = {'leases':['Draft','Active','Ended'], 'work':['Open','Scheduled','In progress','On hold','Completed','Cancelled'], 'expenses':['Unpaid','Paid'], 'inspections':['Scheduled','In progress','Completed'], 'applications':['New','Reviewing','Approved','Declined','Withdrawn'], 'listings':['Draft','Available','Rented'], 'tasks':['To do','Done'], 'tenants':['Current','Prospective','Former'], 'properties':['Active','Inactive']}
CSV_FIELDS={'properties':['name','address','city','region','postal','country','status','type','beds','baths','size','year','market_rent','deposit','amenities','utilities','notes'],'units':['name','property_id','beds','baths','size','market_rent','deposit','notes'],'tenants':['name','status','email','phone','address','emergency_name','emergency_phone','occupants','pets','vehicles','insurance','insurance_expiry','notes'],'vendors':['name','trade','contact','email','phone','address','insurance_expiry','notes'],'expenses':['description','property_id','category','amount','date','due','status','paid_date','vendor_id','payee','work_id','reference','method','cost_type','notes']}

def now(): return datetime.now(timezone.utc).isoformat(timespec='seconds')
def uid(): return uuid.uuid4().hex
def money(value): return f"${Decimal(str(value or 0)):,.2f}"
def cents(value):
    try:
        d = Decimal(str(value))
        if not d.is_finite() or d < 0 or d > Decimal('999999999.99') or d != d.quantize(Decimal('.01')): raise ValueError()
        return int(d * 100)
    except (InvalidOperation, ValueError, TypeError): raise ValueError('Enter a nonnegative amount with at most two decimal places.')

class Store:
    def __init__(self, folder):
        self.folder = Path(folder).resolve()
        self.folder.mkdir(parents=True, exist_ok=True)
        self.uploads = self.folder / 'uploads'
        self.uploads.mkdir(exist_ok=True)
        self.db = self.folder / 'hearth.sqlite3'
        self.lock = threading.RLock()
        with self.connect() as con:
            con.executescript('''
            PRAGMA journal_mode=WAL;
            CREATE TABLE IF NOT EXISTS records(id TEXT PRIMARY KEY, kind TEXT NOT NULL, data TEXT NOT NULL, version INTEGER NOT NULL DEFAULT 1, archived INTEGER NOT NULL DEFAULT 0, created TEXT NOT NULL, updated TEXT NOT NULL);
            CREATE INDEX IF NOT EXISTS by_kind ON records(kind,archived);
            CREATE TABLE IF NOT EXISTS files(id TEXT PRIMARY KEY, record_id TEXT, kind TEXT, name TEXT NOT NULL, mime TEXT, size INTEGER, digest TEXT, created TEXT);
            CREATE TABLE IF NOT EXISTS audit(id INTEGER PRIMARY KEY AUTOINCREMENT, at TEXT, action TEXT, kind TEXT, record_id TEXT, before_json TEXT, after_json TEXT);
            CREATE TABLE IF NOT EXISTS settings(key TEXT PRIMARY KEY, value TEXT);
            CREATE TABLE IF NOT EXISTS receipts(number INTEGER PRIMARY KEY AUTOINCREMENT, payment_id TEXT UNIQUE, snapshot TEXT NOT NULL, created TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS generated(lease_id TEXT, due TEXT, tenant_id TEXT, charge_id TEXT, PRIMARY KEY(lease_id,due,tenant_id));
            ''')
            transfers.initialize(con)
            if not con.execute("SELECT 1 FROM settings WHERE key='initialized'").fetchone():
                defaults = [('Plumbing','Work'),('Electrical','Work'),('HVAC','Work'),('Roofing','Work'),('Painting','Work'),('Flooring','Work'),('Landscaping','Work'),('Cleaning','Work'),('Appliances','Work'),('General repair','Work'),('Capital improvement','Work'),('Utilities','Expense'),('Insurance','Expense'),('Property tax','Expense'),('Mortgage interest','Expense'),('Management','Expense'),('Supplies','Expense'),('Travel','Expense'),('Other','Expense'),('Rent','Income'),('Late fee','Income'),('Other income','Income'),('Security deposit','Deposit')]
                for name, scope in defaults:
                    con.execute('INSERT INTO records VALUES(?,?,?,1,0,?,?)', (uid(),'categories',json.dumps({'name':name,'scope':scope}),now(),now()))
                con.execute('INSERT INTO settings VALUES(?,?)', ('initialized','true'))
                con.execute('INSERT INTO settings VALUES(?,?)', ('owner',json.dumps({'name':'Property owner','business':'Hearth','email':'','address':'','currency':'USD'})))
    @contextmanager
    def connect(self):
        con = sqlite3.connect(self.db, timeout=15)
        con.row_factory = sqlite3.Row
        try:
            with con:
                yield con
        finally:
            con.close()
    def row(self, r):
        return {**json.loads(r['data']), 'id':r['id'],'kind':r['kind'],'version':r['version'],'archived':bool(r['archived']),'created':r['created'],'updated':r['updated']} if r else None
    def get(self, con, record_id): return self.row(con.execute('SELECT * FROM records WHERE id=?',(record_id,)).fetchone())
    def records(self, con, kind, archived=False): return [self.row(r) for r in con.execute('SELECT * FROM records WHERE kind=? AND archived=? ORDER BY created DESC',(kind,int(archived)))]
    def state(self):
        with self.connect() as con:
            result = {k:self.records(con,k) for k in KINDS}
            result['files'] = [dict(r) for r in con.execute('SELECT * FROM files ORDER BY created DESC')]
            result['receipts'] = [{**dict(r),'snapshot':json.loads(r['snapshot'])} for r in con.execute('SELECT number,payment_id,snapshot,created FROM receipts')]
            result['owner'] = json.loads(con.execute("SELECT value FROM settings WHERE key='owner'").fetchone()[0])
            result['archived'] = [self.row(r) for r in con.execute('SELECT * FROM records WHERE archived=1 ORDER BY updated DESC')]
            result['audit'] = [dict(r) for r in con.execute('SELECT id,at,action,kind,record_id FROM audit ORDER BY id DESC LIMIT 100')]
            result['today'] = date.today().isoformat()
            return result
    def validate(self, con, kind, data, record_id=None):
        if kind not in KINDS: raise ValueError('Unknown record type.')
        if not isinstance(data,dict): raise ValueError('Record must be an object.')
        data = {k:v for k,v in data.items() if k not in ('id','kind','version','archived','created','updated','receipt_number')}
        if len(json.dumps(data)) > 150000: raise ValueError('Record is too large.')
        for key in REQUIRED[kind]:
            if data.get(key) is None or str(data.get(key)).strip() == '': raise ValueError(f'{key.replace("_"," ").capitalize()} is required.')
        for key in MONEY_FIELDS.get(kind,[]):
            if data.get(key) not in ('',None): data[key] = cents(data[key])/100
        if kind in ('charges','payments','expenses') and cents(data['amount']) <= 0: raise ValueError('Amount must be greater than zero.')
        for key in ('date','start','end','due','completed_date','paid_date','insurance_expiry'):
            if data.get(key):
                try: date.fromisoformat(data[key])
                except (ValueError,TypeError): raise ValueError(f'Invalid {key.replace("_"," ")} date.')
        for key, refkind in REFERENCES.items():
            if data.get(key):
                ref = self.get(con,data[key])
                if not ref or ref['kind'] != refkind or ref['archived']: raise ValueError(f'Select an active {LABELS[refkind].lower()}.')
                if key in ('unit_id','lease_id','charge_id','work_id') and data.get('property_id') and ref.get('property_id') != data['property_id']: raise ValueError('Linked records must belong to the same property.')
        if kind in STATUS_OPTIONS and data.get('status') not in STATUS_OPTIONS[kind]: raise ValueError('Select a valid status.')
        if kind=='properties' and data.get('photo_id'):
            photo=con.execute('SELECT * FROM files WHERE id=?',(data['photo_id'],)).fetchone()
            if not photo or photo['record_id']!=record_id or photo['mime'] not in ('image/jpeg','image/png','image/webp','image/gif'): raise ValueError('Choose an image attached to this property.')
        if kind == 'leases':
            if data.get('term') not in ('Fixed','Month-to-month'): raise ValueError('Select a lease term.')
            if data['term'] == 'Fixed' and not data.get('end'): raise ValueError('Fixed leases need an end date.')
            if data.get('end') and data['end'] < data['start']: raise ValueError('Lease end must follow its start.')
            data['due_day'] = int(data.get('due_day') or 1)
            if not 1 <= data['due_day'] <= 31: raise ValueError('Due day must be between 1 and 31.')
            co = data.get('co_tenant_id')
            if co:
                tenant = self.get(con,co)
                if not tenant or tenant['kind'] != 'tenants' or tenant['archived'] or co == data['tenant_id']: raise ValueError('Choose a different co-tenant.')
                share = cents(data.get('co_tenant_share') or 0)
                if share > cents(data['rent']): raise ValueError('Co-tenant share cannot exceed rent.')
            elif cents(data.get('co_tenant_share') or 0): raise ValueError('Select the co-tenant for this share.')
        if kind == 'charges' and record_id:
            paid = sum(cents(p['amount']) for p in self.records(con,'payments') if p.get('charge_id') == record_id and not p.get('void'))
            old = self.get(con,record_id)
            if paid and any(data.get(k) != old.get(k) for k in ('tenant_id','property_id','category')): raise ValueError('A charge with payments cannot change its tenant, property or category.')
            if cents(data['amount']) < paid or (data.get('void') and paid): raise ValueError('Void the linked payments first, or keep the charge at least as large as its payments.')
        if kind == 'payments':
            if data.get('charge_id'):
                charge = self.get(con,data['charge_id'])
                if charge.get('void'): raise ValueError('Cannot pay a voided charge.')
                if charge.get('tenant_id') != data['tenant_id']: raise ValueError('Payment tenant must match charge tenant.')
                if charge.get('category') != data.get('category'): raise ValueError('Payment category must match its charge.')
                allocated = sum(cents(p['amount']) for p in self.records(con,'payments') if p['id'] != record_id and p.get('charge_id') == charge['id'] and not p.get('void'))
                if not data.get('void') and allocated + cents(data['amount']) > cents(charge['amount']): raise ValueError('Payment exceeds the remaining charge balance. Record any excess separately.')
            if record_id:
                old = self.get(con,record_id)
                if any(data.get(k) != old.get(k) for k in ('tenant_id','property_id','amount','date','category','charge_id','method','reference')): raise ValueError('Issued payments cannot be rewritten. Void this payment and record a corrected one.')
        if kind == 'expenses':
            if data.get('status') == 'Paid' and not data.get('paid_date'): data['paid_date'] = data['date']
        if kind == 'fields':
            if data['entity'] not in KINDS or data['entity'] in ('fields','categories'): raise ValueError('Invalid custom-field record type.')
            if data['field_type'] not in ('Text','Number','Date','Choice','Yes / No','Long text'): raise ValueError('Invalid field type.')
            if data['field_type']=='Choice' and not str(data.get('options','')).strip(): raise ValueError('Enter at least one choice.')
            if any(f['id']!=record_id and f['entity']==data['entity'] and f['name'].casefold()==data['name'].casefold() for f in self.records(con,'fields')): raise ValueError('A field with that name already exists.')
        custom = data.get('custom',{})
        if not isinstance(custom,dict): raise ValueError('Invalid custom values.')
        for f in self.records(con,'fields'):
            if f['entity'] != kind: continue
            val = custom.get(f['id'])
            if f.get('required') and (val is None or val==''): raise ValueError(f'{f["name"]} is required.')
            if val in ('',None): continue
            if f['field_type']=='Number':
                try:
                    if not Decimal(str(val)).is_finite(): raise ValueError()
                except (ValueError,InvalidOperation): raise ValueError(f'{f["name"]} must be a number.')
            if f['field_type']=='Date':
                try: date.fromisoformat(str(val))
                except ValueError: raise ValueError(f'{f["name"]} must be a date.')
            if f['field_type']=='Choice' and val not in [o.strip() for o in f.get('options','').split(',')]: raise ValueError(f'Select a valid {f["name"]}.')
        return data
    def write(self, con, kind, data, record_id=None, version=None):
        old = self.get(con,record_id) if record_id else None
        if record_id and (not old or old['kind'] != kind): raise ValueError('Record not found.')
        if old and (old['archived'] or version != old['version']): raise ValueError('This record changed or was archived. Refresh and try again.')
        data = self.validate(con,kind,data,record_id)
        if old and kind in ('work','leases','units') and old.get('property_id')!=data.get('property_id'):
            refkey={'work':'work_id','leases':'lease_id','units':'unit_id'}[kind]
            if any(json.loads(r['data']).get(refkey)==record_id for r in con.execute('SELECT data FROM records WHERE archived=0')):
                raise ValueError('This record has linked history and cannot be moved to another property.')
        record_id = record_id or uid()
        if old: con.execute('UPDATE records SET data=?,version=version+1,updated=? WHERE id=?',(json.dumps(data),now(),record_id))
        else: con.execute('INSERT INTO records VALUES(?,?,?,1,0,?,?)',(record_id,kind,json.dumps(data),now(),now()))
        con.execute('INSERT INTO audit(at,action,kind,record_id,before_json,after_json) VALUES(?,?,?,?,?,?)',(now(),'Updated' if old else 'Created',kind,record_id,json.dumps(old) if old else None,json.dumps(data)))
        if kind=='payments' and not old and not data.get('imported_summary'):
            tenant=self.get(con,data['tenant_id']); prop=self.get(con,data['property_id'])
            owner=json.loads(con.execute("SELECT value FROM settings WHERE key='owner'").fetchone()[0])
            snap={**data,'tenant_name':tenant['name'],'property_name':prop['name'],'property_address':prop['address'],'owner':owner}
            con.execute('INSERT INTO receipts(payment_id,snapshot,created) VALUES(?,?,?)',(record_id,json.dumps(snap),now()))
        return self.get(con,record_id)
    def save(self,kind,data,record_id=None,version=None):
        with self.lock,self.connect() as con: return self.write(con,kind,data,record_id,version)
    def create_receipt(self,payment_id):
        with self.lock,self.connect() as con:
            payment=self.get(con,payment_id)
            if not payment or payment['kind']!='payments' or payment['archived']: raise ValueError('Payment not found.')
            if payment.get('void'): raise ValueError('A receipt cannot be created for a voided payment.')
            if con.execute('SELECT 1 FROM receipts WHERE payment_id=?',(payment_id,)).fetchone(): raise ValueError('This payment already has a locked receipt.')
            tenant=self.get(con,payment['tenant_id']); prop=self.get(con,payment['property_id'])
            owner=json.loads(con.execute("SELECT value FROM settings WHERE key='owner'").fetchone()[0])
            snapshot={**payment,'tenant_name':tenant['name'],'property_name':prop['name'],'property_address':prop['address'],'owner':owner}
            cur=con.execute('INSERT INTO receipts(payment_id,snapshot,created) VALUES(?,?,?)',(payment_id,json.dumps(snapshot),now()))
            con.execute('INSERT INTO audit(at,action,kind,record_id) VALUES(?,?,?,?)',(now(),'Receipt created','payments',payment_id))
            return {'number':cur.lastrowid,'payment_id':payment_id}
    def archive(self,record_id,restore=False):
        with self.lock,self.connect() as con:
            old=self.get(con,record_id)
            if not old: raise ValueError('Record not found.')
            if not restore:
                if old['kind'] in ('payments','charges','expenses'): raise ValueError('Financial records are kept permanently. Use Void instead.')
                for r in con.execute('SELECT * FROM records WHERE archived=0 AND id!=?',(record_id,)):
                    d=self.row(r)
                    if record_id in [d.get(k) for k in (*REFERENCES,'co_tenant_id')]: raise ValueError('This record is linked to other records. Keep it and change its status instead.')
            con.execute('UPDATE records SET archived=?,version=version+1,updated=? WHERE id=?',(0 if restore else 1,now(),record_id))
            con.execute('INSERT INTO audit(at,action,kind,record_id,before_json) VALUES(?,?,?,?,?)',(now(),'Restored' if restore else 'Archived',old['kind'],record_id,json.dumps(old)))
    def generate_rent(self,through):
        through=date.fromisoformat(through)
        if through > date(date.today().year+2,12,31): raise ValueError('Generate at most two years ahead.')
        count=0
        with self.lock,self.connect() as con:
            for lease in self.records(con,'leases'):
                if lease.get('status')!='Active' or not lease.get('recurring',True): continue
                start=date.fromisoformat(lease['start']); end=date.fromisoformat(lease['end']) if lease.get('end') and not lease.get('auto_month') else through
                if (through-start).days>366*20: raise ValueError('Lease start is more than 20 years before the requested date.')
                y,m=start.year,start.month
                while date(y,m,1)<=min(through,end):
                    due=date(y,m,min(int(lease.get('due_day',1)),calendar.monthrange(y,m)[1]))
                    if start<=due<=min(through,end):
                        shares=[(lease['tenant_id'],cents(lease['rent'])-cents(lease.get('co_tenant_share',0)))]
                        if lease.get('co_tenant_id'): shares.append((lease['co_tenant_id'],cents(lease.get('co_tenant_share',0))))
                        for tenant,amount in shares:
                            if amount<=0 or con.execute('SELECT 1 FROM generated WHERE lease_id=? AND substr(due,1,7)=? AND tenant_id=?',(lease['id'],due.isoformat()[:7],tenant)).fetchone(): continue
                            charge=self.write(con,'charges',{'tenant_id':tenant,'property_id':lease['property_id'],'unit_id':lease.get('unit_id',''),'lease_id':lease['id'],'date':due.isoformat(),'amount':amount/100,'category':'Rent','description':f'Rent · {due.strftime("%B %Y")}', 'generated':True})
                            con.execute('INSERT INTO generated VALUES(?,?,?,?)',(lease['id'],due.isoformat(),tenant,charge['id']))
                            count+=1
                    y,m=(y+1,1) if m==12 else (y,m+1)
        return {'created':count}
    def add_file(self,data):
        name=Path(str(data.get('name','')).replace('\\','/')).name
        if not name or len(name)>200: raise ValueError('Invalid file name.')
        try: content=base64.b64decode(data['content'],validate=True)
        except Exception: raise ValueError('Invalid upload.')
        if not content or len(content)>20*1024*1024: raise ValueError('Files must be between 1 byte and 20 MB.')
        fid=uid()
        with self.lock,self.connect() as con:
            rid=data.get('record_id','')
            record=self.get(con,rid) if rid else None
            if rid and (not record or record['archived']): raise ValueError('Record not found.')
            mime=mimetypes.guess_type(name)[0] or 'application/octet-stream'
            (self.uploads/fid).write_bytes(content)
            try:
                con.execute('INSERT INTO files VALUES(?,?,?,?,?,?,?,?)',(fid,rid,record['kind'] if record else '',name,mime,len(content),hashlib.sha256(content).hexdigest(),now()))
                con.execute('INSERT INTO audit(at,action,kind,record_id) VALUES(?,?,?,?)',(now(),'File uploaded',record['kind'] if record else 'documents',rid or fid))
            except Exception:
                (self.uploads/fid).unlink(missing_ok=True)
                raise
        return {'id':fid,'name':name}
    def backup(self):
        with self.lock,self.connect() as source:
            backup_path=self.folder/('.backup-'+uid()+'.sqlite3')
            with closing(sqlite3.connect(backup_path)) as dest: source.backup(dest)
            stream=io.BytesIO()
            try:
                with zipfile.ZipFile(stream,'w',zipfile.ZIP_DEFLATED) as z:
                    z.write(backup_path,'hearth.sqlite3')
                    for f in source.execute('SELECT id FROM files'):
                        path=self.uploads/f['id']
                        if not path.is_file(): raise ValueError('An attachment is missing; resolve it before making a complete backup.')
                        z.write(path,'uploads/'+f['id'])
                    z.writestr('manifest.json',json.dumps({'app':'Hearth','format':1,'created':now()}))
            finally: backup_path.unlink(missing_ok=True)
            return stream.getvalue()
    def report(self,params):
        state=self.state(); prop=params.get('property',''); start=params.get('start',''); end=params.get('end',''); tenant=params.get('tenant','')
        def valid(r,dt='date'):
            return not r.get('void') and (not prop or r.get('property_id')==prop) and (not tenant or r.get('tenant_id')==tenant) and (not start or r.get(dt,'')>=start) and (not end or r.get(dt,'')<=end)
        payments=[p for p in state['payments'] if valid(p)]
        expenses=[e for e in state['expenses'] if e.get('status')=='Paid' and valid(e,'paid_date')]
        income=sum(cents(p['amount']) for p in payments if p.get('category')!='Security deposit')
        deposits=sum(cents(p['amount']) for p in payments if p.get('category')=='Security deposit')
        spent=sum(cents(e['amount']) for e in expenses)
        groups={}
        for e in expenses:
            key=e['category']; groups[key]=groups.get(key,0)+cents(e['amount'])
        outstanding=[]
        for c in state['charges']:
            if not valid(c): continue
            paid=sum(cents(p['amount']) for p in state['payments'] if p.get('charge_id')==c['id'] and not p.get('void'))
            if cents(c['amount'])>paid: outstanding.append({**c,'balance':(cents(c['amount'])-paid)/100})
        return {'income':income/100,'expenses':spent/100,'net':(income-spent)/100,'deposits':deposits/100,'categories':[{'name':k,'amount':v/100} for k,v in sorted(groups.items(),key=lambda t:-t[1])],'outstanding':outstanding,'payments':payments,'expense_rows':expenses}

def print_page(title,body):
    return f'''<!doctype html><html><head><meta charset="utf-8"><title>{html.escape(title)}</title><style>body{{font:15px system-ui;max-width:850px;margin:60px auto;padding:25px;color:#243b34}}h1{{font:40px Georgia}}table{{width:100%;border-collapse:collapse;margin:30px 0}}td,th{{padding:13px;text-align:left;border-bottom:1px solid #ddd}}.top{{display:flex;justify-content:space-between}}.muted{{color:#6b7770}}button{{padding:10px 20px;background:#213e35;color:white;border:0;border-radius:8px}}pre{{font:inherit;white-space:pre-wrap}}@media print{{button{{display:none}}body{{margin:0;max-width:none}}}}</style></head><body><div class="top"><strong>HEARTH</strong><button onclick="window.print()">Print / Save as PDF</button></div>{body}</body></html>'''

def oauth_result_page(success,message):
    title='Google Workspace connected' if success else 'Connection unsuccessful'
    color='#24493b' if success else '#a44136'
    payload=json.dumps({'type':'hearth-google-email','connected':success})
    return f'''<!doctype html><html><head><meta charset="utf-8"><title>{title}</title><style>body{{font:16px system-ui;background:#f6f7f2;color:#263c34;display:grid;place-items:center;min-height:100vh;margin:0}}main{{background:white;border:1px solid #e3e7de;border-radius:14px;padding:38px;max-width:520px;box-shadow:0 18px 60px #24493b20}}h1{{font:32px Georgia;color:{color}}}p{{line-height:1.7}}</style></head><body><main><h1>{html.escape(title)}</h1><p>{html.escape(message)}</p></main><script>if(window.opener){{window.opener.postMessage({payload},location.origin);if({str(success).lower()})setTimeout(()=>window.close(),900)}}</script></body></html>'''

class Handler(BaseHTTPRequestHandler):
    server_version='Hearth/1.0'
    def log_message(self,fmt,*args):
        if args and str(args[1] if len(args)>1 else '') not in ('200','304'): super().log_message(fmt,*args)
    @property
    def store(self): return self.server.store
    def send(self,status,data,ctype='application/json',headers=None):
        if isinstance(data,(dict,list)): data=json.dumps(data).encode()
        elif isinstance(data,str): data=data.encode()
        self.send_response(status)
        self.send_header('Content-Type',ctype)
        self.send_header('Content-Length',str(len(data)))
        self.send_header('Cache-Control','no-store')
        self.send_header('X-Content-Type-Options','nosniff')
        self.send_header('X-Frame-Options','DENY')
        self.send_header('Referrer-Policy','no-referrer')
        self.send_header('Content-Security-Policy',"default-src 'self'; style-src 'self' 'unsafe-inline'; script-src 'self' 'unsafe-inline'; img-src 'self' data: blob:; object-src 'none'; frame-ancestors 'none'; base-uri 'none'; connect-src 'self'")
        for k,v in (headers or {}).items(): self.send_header(k,v)
        self.end_headers(); self.wfile.write(data)
    def authenticated(self):
        if not getattr(self.server,'public',False): return True
        header=self.headers.get('Authorization','')
        if not header.startswith('Basic '): return False
        try:
            username,password=base64.b64decode(header[6:],validate=True).decode('utf-8').split(':',1)
        except (ValueError,UnicodeDecodeError):
            return False
        return secrets.compare_digest(username,getattr(self.server,'auth_username','owner')) and secrets.compare_digest(password,getattr(self.server,'auth_password',''))
    def reject_access(self):
        if getattr(self.server,'public',False) and not self.authenticated():
            return self.send(401,{'error':'Sign in to Hearth.'},headers={'WWW-Authenticate':'Basic realm="Hearth", charset="UTF-8"'})
        return self.send(403,{'error':'Local access only.'})
    def allowed(self,mutation=False):
        if not self.authenticated(): return False
        host=self.headers.get('Host','')
        origin=self.headers.get('Origin')
        if getattr(self.server,'public',False):
            if not host or any(char in host for char in ('\r','\n','/')): return False
            if origin:
                parsed=urlsplit(origin)
                if parsed.scheme not in ('http','https') or parsed.netloc!=host: return False
        else:
            if host not in (f'127.0.0.1:{self.server.server_port}',f'localhost:{self.server.server_port}'): return False
            if origin and origin not in (f'http://127.0.0.1:{self.server.server_port}',f'http://localhost:{self.server.server_port}'): return False
        if mutation and not secrets.compare_digest(self.headers.get('X-Hearth-Token',''),self.server.token): return False
        return True
    def do_GET(self):
        u=urlsplit(self.path); path=u.path; params={k:v[0] for k,v in parse_qs(u.query).items()}
        if path=='/healthz': return self.send(200,{'ok':True,'application':'hearth'})
        if not self.allowed(): return self.reject_access()
        try:
            if path=='/api/state': return self.send(200,{**self.store.state(),'email_service':self.server.email_service.status(),'token':self.server.token,'demo':self.server.demo,'application':'hearth'})
            if path=='/oauth/google/callback':
                if params.get('error'): return self.send(400,oauth_result_page(False,'Google did not connect Hearth: '+params['error']),'text/html; charset=utf-8')
                try:
                    self.server.email_service.finish(params.get('code',''),params.get('state',''))
                    return self.send(200,oauth_result_page(True,'Google Workspace is connected. You can close this window.'),'text/html; charset=utf-8')
                except ValueError as ex:
                    return self.send(400,oauth_result_page(False,str(ex)),'text/html; charset=utf-8')
            if path=='/api/report': return self.send(200,self.store.report(params))
            if path=='/api/transfers/history': return self.send(200,transfers.history(self.store))
            if path=='/api/transfers/source-history':
                with self.store.connect() as con:
                    rows=[{**dict(r),'raw':json.loads(r['raw'])} for r in con.execute("SELECT source_key,category,raw,disposition FROM transfer_sources WHERE disposition='preserved'")]
                return self.send(200,rows)
            if path.startswith('/api/transfers/original/'):
                with self.store.connect() as con: original=con.execute('SELECT * FROM transfer_originals WHERE id=?',(path.rsplit('/',1)[1],)).fetchone()
                if not original: return self.send(404,{'error':'Original file not found.'})
                return self.send(200,original['content'],'application/octet-stream',{'Content-Disposition':"attachment; filename*=UTF-8''"+quote(original['name'])})
            if path=='/api/transfers/export-preview':
                summary,_=transfers.export_tenantcloud(self.store.state(),params.get('section'),params.get('scope','all'))
                return self.send(200,{k:v for k,v in summary.items() if k!='rows'})
            if path=='/api/transfers/export':
                summary,chunks=transfers.export_tenantcloud(self.store.state(),params.get('section'),params.get('scope','all'))
                if summary['errors']: raise ValueError('Resolve export errors shown in the preview first.')
                section=summary['section']
                if len(chunks)==1: return self.send(200,transfers.csv_bytes(summary['headers'],chunks[0]),'text/csv; charset=utf-8',{'Content-Disposition':f'attachment; filename="TenantCloud_{section}.csv"'})
                output=io.BytesIO()
                with zipfile.ZipFile(output,'w',zipfile.ZIP_DEFLATED) as z:
                    for i,rows in enumerate(chunks,1): z.writestr(f'TenantCloud_{section}_{i}.csv',transfers.csv_bytes(summary['headers'],rows))
                return self.send(200,output.getvalue(),'application/zip',{'Content-Disposition':f'attachment; filename="TenantCloud_{section}.zip"'})
            if path=='/api/backup': return self.send(200,self.store.backup(),'application/zip',{'Content-Disposition':f'attachment; filename="hearth-backup-{date.today()}.zip"'})
            if path.startswith('/api/export/'):
                kind=path.rsplit('/',1)[1]
                if kind not in KINDS: raise ValueError('Unknown export.')
                state=self.store.state(); rows=state[kind]
                cols=sorted({k for r in rows for k in r if k not in ('custom',)} or set(CSV_FIELDS.get(kind,REQUIRED[kind])))
                cols+=['custom.'+f['name'] for f in state['fields'] if f['entity']==kind]
                output=io.StringIO(); writer=csv.DictWriter(output,fieldnames=cols); writer.writeheader()
                for r in rows:
                    values={k:r.get(k,'') for k in cols}
                    for f in state['fields']:
                        if f['entity']==kind: values['custom.'+f['name']]=r.get('custom',{}).get(f['id'],'')
                    for k,v in values.items():
                        if isinstance(v,(dict,list)): v=json.dumps(v)
                        s=str(v)
                        values[k]="'"+s if s.startswith(('=','+','-','@','\t','\r')) else s
                    writer.writerow(values)
                return self.send(200,'\ufeff'+output.getvalue(),'text/csv; charset=utf-8',{'Content-Disposition':f'attachment; filename="hearth-{kind}.csv"'})
            if path.startswith('/api/files/'):
                fid=path.rsplit('/',1)[1]
                with self.store.connect() as con: f=con.execute('SELECT * FROM files WHERE id=?',(fid,)).fetchone()
                if not f: return self.send(404,{'error':'File not found.'})
                data=(self.store.uploads/fid).read_bytes()
                safe=f['mime'] in ('application/pdf','image/png','image/jpeg','image/webp','image/gif')
                return self.send(200,data,f['mime'] if safe else 'application/octet-stream',{'Content-Disposition':f'{"inline" if safe else "attachment"}; filename*=UTF-8\'\'{quote(f["name"])}'})
            if path.startswith('/receipt/'):
                receipt_part=path.rsplit('/',1)[1]; wants_pdf=receipt_part.endswith('.pdf'); number=receipt_part.removesuffix('.pdf')
                with self.store.connect() as con:
                    r=con.execute('SELECT * FROM receipts WHERE number=?',(number,)).fetchone()
                    if not r: return self.send(404,{'error':'Receipt not found.'})
                    d=json.loads(r['snapshot']); p=self.store.get(con,r['payment_id'])
                e=html.escape; owner=d['owner']; ref=f'R-{int(number):05}'
                if wants_pdf:
                    pdf_snapshot={**d,'void':bool(p and p.get('void'))}
                    return self.send(200,create_receipt_pdf(pdf_snapshot,ref),'application/pdf',{'Content-Disposition':f'inline; filename="{ref}-payment-receipt.pdf"'})
                body=f'<h1>Payment receipt</h1><p class="muted">{ref} · {e(d["date"])}</p>'
                if p and p.get('void'): body+='<h2>VOID — not a valid receipt</h2>'
                body+=f'<h3>{e(owner.get("business") or owner["name"])}</h3><p>{e(owner.get("address",""))}<br>{e(owner.get("email",""))}</p><table>'
                for label,value in [('Received from',d['tenant_name']),('Property',d['property_name']),('Address',d['property_address']),('For',d['category']),('Description',d.get('description','')),('Amount received',money(d['amount'])),('Payment method',d.get('method','')),('Reference',d.get('reference',''))]: body+=f'<tr><th>{label}</th><td>{e(str(value))}</td></tr>'
                body+='</table><p class="muted">This receipt records a payment entered by the property owner.</p>'
                return self.send(200,print_page(ref,body),'text/html; charset=utf-8')
            if path.startswith('/lease/'):
                rid=path.rsplit('/',1)[1]
                with self.store.connect() as con:
                    d=self.store.get(con,rid)
                    if not d or d['kind']!='leases': return self.send(404,{'error':'Lease not found.'})
                    p=self.store.get(con,d['property_id']); t=self.store.get(con,d['tenant_id'])
                e=html.escape
                body=f'<h1>Lease summary</h1><p class="muted">{e(d["name"])}</p><table>'
                for k,v in [('Property',p['name']),('Address',p['address']),('Tenant',t['name']),('Term',d['term']),('Start',d['start']),('End',d.get('end') or 'Month-to-month'),('Monthly rent',money(d['rent'])),('Security deposit',money(d.get('deposit',0))),('Rent due day',d.get('due_day',1)),('Status',d['status'])]: body+=f'<tr><th>{k}</th><td>{e(str(v))}</td></tr>'
                body+='</table><h3>Terms and notes</h3><pre>'+e(d.get('notes',''))+'</pre><p class="muted">Management summary. Keep your signed lease document attached to this record.</p>'
                return self.send(200,print_page('Lease summary',body),'text/html; charset=utf-8')
            file=ROOT/'static'/('index.html' if path=='/' else path.lstrip('/'))
            if not file.resolve().is_relative_to((ROOT/'static').resolve()) or not file.is_file(): return self.send(404,{'error':'Not found.'})
            return self.send(200,file.read_bytes(),mimetypes.guess_type(str(file))[0] or 'application/octet-stream')
        except ValueError as ex: self.send(400,{'error':str(ex)})
        except Exception as ex:
            print('Read error:',type(ex).__name__,str(ex),file=sys.stderr)
            self.send(500,{'error':'Could not read the requested data.'})
    def do_POST(self):
        if not self.allowed(True):
            if getattr(self.server,'public',False) and not self.authenticated(): return self.reject_access()
            return self.send(403,{'error':'Refresh the app before saving.'})
        try:
            length=int(self.headers.get('Content-Length','0'))
            if length<=0 or length>29*1024*1024: return self.send(413,{'error':'Request is too large or empty.'})
            data=json.loads(self.rfile.read(length)); path=urlsplit(self.path).path
            if path=='/api/save': result=self.store.save(data['kind'],data['data'],data.get('id'),data.get('version'))
            elif path=='/api/receipts/create': result=self.store.create_receipt(data['payment_id'])
            elif path=='/api/email/google/configure': result=self.server.email_service.configure(data.get('content',''),data.get('email',''))
            elif path=='/api/email/google/start':
                if getattr(self.server,'public',False) and not getattr(self.server,'base_url',''):
                    raise ValueError('Set HEARTH_BASE_URL to your HTTPS app address before connecting Google Workspace.')
                redirect=(getattr(self.server,'base_url','') or f'http://127.0.0.1:{self.server.server_port}')+'/oauth/google/callback'
                result=self.server.email_service.start(redirect)
            elif path=='/api/email/google/disconnect': result=self.server.email_service.disconnect()
            elif path=='/api/email/send-receipt': result=self.server.email_service.send_receipt(self.store,data['payment_id'])
            elif path=='/api/archive': self.store.archive(data['id'],data.get('restore',False)); result={'ok':True}
            elif path=='/api/generate': result=self.store.generate_rent(data['through'])
            elif path=='/api/upload': result=self.store.add_file(data)
            elif path=='/api/transfers/preview':
                if data.get('source')!='tenantcloud': raise ValueError('Choose a supported import application.')
                files=transfers.decode_files(data.get('files'))
                summary,fingerprint=transfers.preview(self.store,files)
                token=secrets.token_urlsafe(24)
                if not hasattr(self.server,'transfer_previews'): self.server.transfer_previews={}
                # Bounded in-memory previews. Uploaded files are persisted only on import.
                if len(self.server.transfer_previews)>=8: self.server.transfer_previews.pop(next(iter(self.server.transfer_previews)))
                self.server.transfer_previews[token]=(files,fingerprint,summary)
                result={**summary,'preview_id':token}
            elif path=='/api/transfers/commit':
                previews=getattr(self.server,'transfer_previews',{})
                pending=previews.get(data.get('preview_id'))
                if not pending: raise ValueError('Preview expired. Select the files and preview again.')
                result=transfers.commit(self.store,*pending)
                previews.pop(data['preview_id'],None)
            elif path=='/api/owner':
                owner={k:str(data.get(k,''))[:1000] for k in ('name','business','email','address')}; owner['currency']='USD'
                with self.store.lock,self.store.connect() as con: con.execute("UPDATE settings SET value=? WHERE key='owner'",(json.dumps(owner),))
                result={'ok':True}
            elif path=='/api/import':
                kind=data['kind']; rows=data['rows']
                if kind not in ('properties','units','tenants','vendors','expenses') or not isinstance(rows,list) or len(rows)>1000: raise ValueError('Import up to 1,000 properties, units, tenants, vendors or expenses at a time.')
                with self.store.lock,self.store.connect() as con:
                    for i,row in enumerate(rows):
                        try:
                            row=dict(row)
                            row['custom']=row.get('custom',{})
                            for f in self.store.records(con,'fields'):
                                key='custom.'+f['name']
                                if f['entity']==kind and key in row:
                                    val=row.pop(key)
                                    row['custom'][f['id']]=(str(val).lower() in ('true','yes','1')) if f['field_type']=='Yes / No' else val
                            self.store.write(con,kind,row)
                        except ValueError as ex: raise ValueError(f'Row {i+1}: {ex}')
                result={'created':len(rows)}
            else: return self.send(404,{'error':'Unknown action.'})
            self.send(200,result)
        except (ValueError,KeyError,TypeError) as ex: self.send(400,{'error':str(ex)})
        except Exception as ex:
            print('Save error:',type(ex).__name__,str(ex),file=sys.stderr)
            self.send(500,{'error':'The change could not be saved. Your existing data is unchanged.'})

def main():
    parser=argparse.ArgumentParser(description='Hearth local property management')
    parser.add_argument('--host',default=os.environ.get('HEARTH_HOST','127.0.0.1'))
    parser.add_argument('--port',type=int,default=int(os.environ.get('PORT','8768')))
    parser.add_argument('--data-dir',default=os.environ.get('HEARTH_DATA_DIR',str(ROOT/'data')))
    parser.add_argument('--demo',action='store_true',help='Label this separate workspace as a sample preview')
    args=parser.parse_args()
    public=args.host not in ('127.0.0.1','localhost','::1')
    password=os.environ.get('HEARTH_PASSWORD','')
    if public and len(password)<12:
        parser.error('HEARTH_PASSWORD must be set to at least 12 characters before Hearth can listen beyond this computer.')
    base_url=os.environ.get('HEARTH_BASE_URL','').rstrip('/')
    if base_url and (not base_url.startswith('https://') or urlsplit(base_url).path not in ('','/')):
        parser.error('HEARTH_BASE_URL must be an HTTPS origin without a path, such as https://hearth.example.com')
    server=ThreadingHTTPServer((args.host,args.port),Handler)
    server.store=Store(args.data_dir); server.email_service=GoogleWorkspaceEmail(args.data_dir); server.token=secrets.token_urlsafe(32); server.demo=args.demo
    server.public=public; server.auth_username=os.environ.get('HEARTH_USERNAME','owner'); server.auth_password=password; server.base_url=base_url
    print(f'Hearth is ready on {args.host}:{args.port}',flush=True)
    try: server.serve_forever()
    except KeyboardInterrupt: pass
    finally: server.server_close()
if __name__=='__main__': main()
