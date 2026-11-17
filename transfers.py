"""Versioned, local-only data adapters. TenantCloud schemas observed 2026-09-30.

Never infer the producer from a filename. Exact header signatures select parsers;
relationships are resolved explicitly and unresolved rows remain in source history.
"""
from __future__ import annotations
import base64
import csv
import hashlib
import io
import json
import posixpath
import re
import sqlite3
import uuid
import zipfile
from collections import Counter
from datetime import datetime, date, timedelta
from decimal import Decimal, InvalidOperation
from pathlib import PurePosixPath
from xml.etree import ElementTree as ET

VERSION = 'tenantcloud-2026-09-30'
MAX_BYTES = 20 * 1024 * 1024
MAX_EXPANDED = 100 * 1024 * 1024
PROPERTY = ['Property name','Unit #','Street address','City','State/Region','Zip','Country','Year built','Unit type','Unit size','Beds','Baths','Market rent','Deposit']
PROPERTY_DETAIL = ['Property name','Street address','City','State/Region','Zip','Country','Year built','Currency','Mls #','Unit type','Beds','Baths','Unit size, ft2','Market rent','Deposit','Parking','Laundry','Air conditioning','Property features','Property amenities']
TENANT = ['First name','Middle name','Last name','Company name','Date of birth','Primary email','Additional email','Primary phone','Additional phone','Street address','Unit/Ap. #','City','State/Region','Zip','Country']
TENANT_DETAIL = ['First name','Middle name','Last name','Company name','Date of birth','Primary email','Additional email 1','Additional email 2','Primary phone','Additional phone 1','Additional phone 2','Street address','Unit/Ap. #','City','State/Region','Zip','Country']
LEASE = ['Lease #','Status','Lease type','Date created','Start date','End date','Tenant full name','Tenant email','Invoicing type','Currency','Rent amount','Rent schedule','Rent due date','First invoice date','Property name','Unit #','Street address','City','State/Region','Zip','Country']
LEASE_DETAIL = [h for h in LEASE if h not in ('Tenant full name','Tenant email','Invoicing type')]
RESIDENTS = ['Type','Full name','Relation','Date of birth','Email','Phone']
TRANSACTION = ['Transaction ID','Status','Date created','Due date','Date paid','Type','Transaction category','Currency','Total amount','Paid amount','Left amount','Method of payment','Payer/payee','Payer/payee email','Lease #','Property name','Unit #','Street address','City','State/Region','Zip','Country','Transaction details','Tags']
LEASE_TEMPLATE = ['Property name*','Unit #*','Street address*','City*','State/Region*','Zip*','Country*','Unit type*','Tenant(s) Full name*','Tenant(s) Company name','Tenant(s) email address','Tenant portal share*','Lease start date*','Lease end date*','Invoicing type','Total recurring rent amount','Tenant rent portion','First rent invoice day','Mark past rent invoices as paid','Rent schedule','Total deposit amount','Tenant deposit portion','Deposit invoice date']
PROPERTY_TEMPLATE = [h+'*' if h in ('Property name','Unit #','Street address','City','State/Region','Zip','Country','Unit type') else h for h in PROPERTY]
TENANT_TEMPLATE = [h+'*' if h in ('First name','Last name') else h for h in TENANT]
SIGNATURES = [('properties',PROPERTY),('property_details',PROPERTY_DETAIL),('tenants',TENANT),('tenant_details',TENANT_DETAIL),('leases',LEASE),('lease_details',LEASE_DETAIL),('residents',RESIDENTS),('transactions',TRANSACTION)]
SECTIONS = {'properties':'Properties & units','tenants':'Tenants','leases':'Leases','transactions':'Transactions','maintenance':'Maintenance','attachments':'Receipt and document files'}

def initialize(con):
    con.executescript('''
    CREATE TABLE IF NOT EXISTS transfer_batches(id TEXT PRIMARY KEY, created TEXT, source TEXT, summary TEXT);
    CREATE TABLE IF NOT EXISTS transfer_sources(source_key TEXT PRIMARY KEY, fingerprint TEXT, category TEXT, raw TEXT, outputs TEXT, disposition TEXT, batch_id TEXT);
    CREATE TABLE IF NOT EXISTS transfer_originals(id TEXT PRIMARY KEY, batch_id TEXT, name TEXT, content BLOB, digest TEXT);
    ''')

def clean(v):
    if v is None or v == '-': return ''
    return str(v).strip()

def norm(v): return re.sub(r'\s+',' ',clean(v)).casefold()
def digest(obj): return hashlib.sha256(json.dumps(obj,sort_keys=True,ensure_ascii=False,default=str).encode()).hexdigest()
def amount(v):
    try:
        n=Decimal(clean(v) or '0')
        if not n.is_finite() or n < 0 or n > Decimal('999999999.99') or n != n.quantize(Decimal('.01')): raise ValueError()
        return int(n*100)
    except (InvalidOperation,ValueError): raise ValueError('Invalid monetary amount; no rounding was performed.')

def iso(v):
    s=clean(v)
    if not s: return ''
    for fmt in ('%b %d, %Y','%Y-%m-%d','%m/%d/%Y'):
        try: return datetime.strptime(s,fmt).date().isoformat()
        except ValueError: pass
    raise ValueError('Unrecognized date: '+s)

def checked_zip(data):
    try: z=zipfile.ZipFile(io.BytesIO(data))
    except zipfile.BadZipFile: raise ValueError('Invalid ZIP or Excel file.')
    infos=z.infolist()
    if len(infos)>5000 or sum(i.file_size for i in infos)>MAX_EXPANDED:
        z.close(); raise ValueError('Archive expands beyond the supported 100 MB / 5,000-file limit.')
    seen=set()
    for i in infos:
        p=PurePosixPath(i.filename.replace('\\','/'))
        if p.is_absolute() or '..' in p.parts or ':' in i.filename or i.filename in seen or i.flag_bits & 1:
            z.close(); raise ValueError('Unsafe, duplicate, or encrypted archive entry.')
        seen.add(i.filename)
    return z

def xml(data):
    if b'<!DOCTYPE' in data.upper() or b'<!ENTITY' in data.upper(): raise ValueError('Unsupported XML declarations.')
    return ET.fromstring(data)

def xlsx(data):
    """Read values only; formulas, external links, macros and executable data are not run."""
    ns={'s':'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
    with checked_zip(data) as z:
        names=z.namelist()
        if 'xl/workbook.xml' not in names: raise ValueError('This file is not an XLSX workbook.')
        strings=[]
        if 'xl/sharedStrings.xml' in names:
            strings=[''.join(n.itertext()) for n in xml(z.read('xl/sharedStrings.xml')).findall('s:si',ns)]
        wb=xml(z.read('xl/workbook.xml'))
        rels={r.attrib['Id']:r.attrib['Target'] for r in xml(z.read('xl/_rels/workbook.xml.rels')) if r.attrib.get('TargetMode')!='External'}
        date_styles=set()
        if 'xl/styles.xml' in names:
            styles=xml(z.read('xl/styles.xml')); custom={int(n.attrib['numFmtId']):n.attrib.get('formatCode','') for n in styles.findall('s:numFmts/s:numFmt',ns)}
            for i,n in enumerate(styles.findall('s:cellXfs/s:xf',ns)):
                num=int(n.attrib.get('numFmtId','0'))
                if num in range(14,23) or (num in custom and re.search(r'[yd]',custom[num],re.I)): date_styles.add(i)
        for sheet in wb.findall('s:sheets/s:sheet',ns):
            target=rels.get(sheet.attrib.get('{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id'))
            if not target: raise ValueError('External worksheets are not supported.')
            path=target.lstrip('/') if target.startswith('/') else posixpath.normpath('xl/'+target)
            rows=[]
            for row in xml(z.read(path)).findall('s:sheetData/s:row',ns):
                cells={}
                for cell in row.findall('s:c',ns):
                    if cell.find('s:f',ns) is not None: raise ValueError('Formula cells are not accepted; export values only.')
                    ref=cell.attrib.get('r','A1'); letters=re.match('[A-Z]+',ref)
                    if not letters: raise ValueError('Invalid worksheet cell.')
                    col=0
                    for ch in letters[0]: col=col*26+ord(ch)-64
                    if col>256: raise ValueError('Too many worksheet columns.')
                    value=cell.findtext('s:v',default='',namespaces=ns); typ=cell.attrib.get('t')
                    if typ=='s': value=strings[int(value)]
                    elif typ=='inlineStr': value=''.join(cell.find('s:is',ns).itertext())
                    elif typ=='e': raise ValueError('Spreadsheet contains an error cell.')
                    elif value and int(cell.attrib.get('s','0')) in date_styles:
                        if wb.find('s:workbookPr',ns) is not None and wb.find('s:workbookPr',ns).attrib.get('date1904')=='1': raise ValueError('1904 date workbooks are not supported; use CSV.')
                        value=(date(1899,12,30)+timedelta(days=float(value))).isoformat()
                    cells[col-1]=value
                values=[cells.get(i,'') for i in range(max(cells,default=-1)+1)]
                if any(clean(v) for v in values): rows.append(values)
                if len(rows)>10001: raise ValueError('Import at most 10,000 rows per worksheet.')
            yield sheet.attrib['name'],rows

def table(rows,filename,sheet):
    if not rows: return None
    if len(rows)>10001: raise ValueError('Import at most 10,000 rows per worksheet or CSV.')
    headers=[clean(v).rstrip('*').strip() for v in rows[0]]
    while headers and not headers[-1]: headers.pop()
    if not headers or len(set(headers))!=len(headers) or any(not h for h in headers): raise ValueError('Blank or duplicate column headings.')
    kind=next((k for k,h in SIGNATURES if headers==h),None)
    if kind is None: return None
    output=[]
    for i,values in enumerate(rows[1:],2):
        if any(clean(v) for v in values[len(headers):]): raise ValueError(f'Row {i} contains extra columns.')
        values=values+['']*(len(headers)-len(values))
        output.append({'row':i,'data':dict(zip(headers,values)),'file':filename,'sheet':sheet})
    return {'kind':kind,'rows':output,'file':filename,'sheet':sheet,'headers':headers}

def decode_files(files):
    if not isinstance(files,list) or not 1<=len(files)<=100: raise ValueError('Choose 1–100 files.')
    result=[]; total=0
    for f in files:
        name=PurePosixPath(str(f.get('name','')).replace('\\','/')).name
        try: content=base64.b64decode(f['content'],validate=True)
        except Exception: raise ValueError('Invalid file content.')
        total+=len(content)
        if not name or not content or total>MAX_BYTES: raise ValueError('Choose files totaling no more than 20 MB.')
        result.append((name,content))
    return result

def parse_files(files):
    tables=[]; issues=[]; inventory=[]; attachments=[]; expanded=0
    def read_one(name,data,in_archive=False):
        nonlocal expanded
        expanded+=len(data)
        if expanded>MAX_EXPANDED: raise ValueError('Combined archive contents exceed 100 MB.')
        ext=PurePosixPath(name).suffix.lower()
        if ext=='.zip':
            if in_archive: raise ValueError('Nested ZIP archives are not supported.')
            with checked_zip(data) as z:
                for info in z.infolist():
                    if not info.is_dir(): read_one(info.filename,z.read(info),True)
            return
        if ext not in ('.csv','.xlsx'):
            attachments.append(name)
            inventory.append({'file':name,'section':'Original file','rows':0})
            return
        try:
            if ext=='.csv':
                try: text=data.decode('utf-8-sig')
                except UnicodeDecodeError: raise ValueError('Use UTF-8 CSV or the original XLSX file.')
                sheets=[('CSV',list(csv.reader(io.StringIO(text),strict=True)))]
            else: sheets=xlsx(data)
            found=False
            for sheet,rows in sheets:
                parsed=table(rows,name,sheet)
                if parsed:
                    tables.append(parsed);found=True
                    inventory.append({'file':name,'sheet':sheet,'section':parsed['kind'],'rows':len(parsed['rows'])})
                elif rows:
                    issues.append({'file':name,'sheet':sheet,'reason':'Unrecognized column layout; preserved in original file only.'})
            if not found and not in_archive: issues.append({'file':name,'reason':'Not in the correct TenantCloud format.'})
        except (ValueError,ET.ParseError,KeyError,IndexError,csv.Error) as ex:
            issues.append({'file':name,'reason':str(ex)})
    for name,data in files: read_one(name,data)
    if not tables: raise ValueError('The file is not in the correct TenantCloud format. Choose an original account export ZIP, recognized XLSX workbook, or CSV with the unchanged TenantCloud column headings.')
    return tables,issues,inventory,attachments

def state_fingerprint(con):
    rows=[tuple(r) for r in con.execute('SELECT id,version,archived FROM records ORDER BY id')]
    rows += [tuple(r) for r in con.execute('SELECT source_key,fingerprint FROM transfer_sources ORDER BY source_key')]
    return digest(rows)

def source_identity(kind,r):
    if kind=='transactions': return 'transaction:'+clean(r['Transaction ID'])
    if kind=='properties': return 'property:'+digest([norm(r.get(k)) for k in ('Property name','Street address','City','State/Region','Zip','Country')])
    if kind=='tenants': return 'tenant:'+digest([norm(r.get(k)) for k in ('First name','Middle name','Last name','Primary email')])
    if kind=='leases': return 'lease:'+digest([norm(r.get(k)) for k in ('Property name','Unit #','Street address','Lease #','Start date')]+[sorted(norm(n) for n in clean(r.get('Tenant full name')).split(',') if clean(n))])
    return kind+':'+digest(r)

def prepare_rows(tables):
    main={k:[] for k in ('properties','tenants','leases','transactions')}
    details={'property_details':{},'tenant_details':{},'lease_details':{}}
    for t in tables:
        for entry in t['rows']:
            r=entry['data'];k=t['kind']
            if k=='property_details': details[k][(norm(r.get('Street address')),norm(r.get('Property name')))]=entry
            if k=='tenant_details': details[k][(norm(r.get('Primary email')),norm(r.get('First name')),norm(r.get('Last name')))]=entry
            if k=='lease_details': details[k][(norm(r.get('Street address')),clean(r.get('Lease #')),clean(r.get('Start date')))]=entry
            if k in main: main[k].append(entry)
    for entry in main['properties']:
        r=entry['data'];d=details['property_details'].pop((norm(r.get('Street address')),norm(r.get('Property name'))),None)
        if d: entry['data']={**d['data'],**r}
    for entry in main['tenants']:
        r=entry['data'];d=details['tenant_details'].pop((norm(r.get('Primary email')),norm(r.get('First name')),norm(r.get('Last name'))),None)
        if d: entry['data']={**d['data'],**r}
    main['properties']+=list(details['property_details'].values())
    main['tenants']+=list(details['tenant_details'].values())
    if not main['leases']:
        for entry in details['lease_details'].values():
            residents=[e['data'] for t in tables if t['file']==entry['file'] and t['kind']=='residents' for e in t['rows'] if e['data'].get('Type')=='Tenant']
            entry['data']={**entry['data'],'Tenant full name':', '.join(clean(r['Full name']) for r in residents),'Tenant email':', '.join(clean(r['Email']) for r in residents)}
            main['leases'].append(entry)
    return main

def run_import(store,con,tables,batch_id):
    # Keep row savepoints inside one transaction; releasing a top-level savepoint
    # would otherwise commit each row before the batch itself succeeds.
    if not con.in_transaction: con.execute('BEGIN')
    main=prepare_rows(tables); counts=Counter(); issues=[]; warnings=set(); outcomes=[]
    previous_leases={source_identity('leases',json.loads(row['raw'])):row for row in con.execute("SELECT * FROM transfer_sources WHERE category='leases'")}
    def find_one(kind,predicate):
        found=[r for r in store.records(con,kind) if predicate(r)]
        if len(found)>1: raise ValueError('More than one matching '+kind+' record. Resolve the duplicate before importing this row.')
        return found[0] if found else None
    def property_for(r,required=True):
        address=norm(r.get('Street address'));name=norm(r.get('Property name'))
        if not address and not name:
            if required: raise ValueError('Property information is missing.')
            return None
        p=find_one('properties',lambda p:norm(p.get('address'))==address and norm(p.get('name'))==name and (not clean(r.get('Zip')) or norm(p.get('postal'))==norm(r['Zip'])))
        if not p: raise ValueError('Matching property is missing. Include its property export or add it to Hearth, then import this file again.')
        return p
    def tenant_for(name,email):
        t=find_one('tenants',lambda t:norm(t.get('email'))==norm(email)) if clean(email) else None
        if not t and clean(name):t=find_one('tenants',lambda t:norm(t.get('name'))==norm(name) or norm(t.get('source_display_name'))==norm(name))
        if not t: raise ValueError('Matching tenant is missing. Include the tenant export or add the tenant, then import this file again.')
        return t
    def save(kind,data,key,raw):
        data={**data,'source_system':'TenantCloud','source_key':key,'source_raw':raw,'import_batch':batch_id}
        result=store.write(con,kind,data);counts[kind]+=1
        return result
    for kind in main:
        for entry in main[kind]:
            r=entry['data'];key=source_identity(kind,r)
            if kind=='properties' and clean(r.get('Unit #')): key+=':unit:'+norm(r['Unit #'])
            fingerprint=digest(r);existing=con.execute('SELECT * FROM transfer_sources WHERE source_key=?',(key,)).fetchone()
            if not existing and kind=='leases': existing=previous_leases.get(key)
            if existing and existing['disposition'] in ('created','matched','preserved'):
                if existing['fingerprint']==fingerprint:
                    counts['duplicates']+=1;continue
                issues.append({**{k:entry[k] for k in ('file','row','sheet')},'reason':'A previously imported source record has changed. Existing Hearth data was kept; automatic replacement is disabled.'});continue
            output=[];disposition='created';con.execute('SAVEPOINT transfer_row'); before=counts.copy()
            try:
                if clean(r.get('Currency')) not in ('','USD'): raise ValueError('This workspace uses USD; this row has a different currency.')
                if kind=='properties':
                    unit=clean(r.get('Unit #'));address=clean(r.get('Street address'));name=clean(r.get('Property name'))
                    p=find_one('properties',lambda p:norm(p.get('address'))==norm(address) and norm(p.get('name'))==norm(name) and norm(p.get('postal'))==norm(r.get('Zip')))
                    if not p:
                        p=save('properties',{'name':name,'address':address,'city':clean(r.get('City')),'region':clean(r.get('State/Region')),'postal':clean(r.get('Zip')),'country':clean(r.get('Country')),'year':clean(r.get('Year built')),'type':'Multi unit' if unit else 'Single family','source_unit_type':clean(r.get('Unit type')),'status':'Active','beds':clean(r.get('Beds')),'baths':clean(r.get('Baths')),'size':clean(r.get('Unit size',r.get('Unit size, ft2'))),'market_rent':amount(r.get('Market rent'))/100,'deposit':amount(r.get('Deposit'))/100,'amenities':'\n'.join(k+': '+clean(r[k]) for k in ('Parking','Laundry','Air conditioning','Property features','Property amenities') if clean(r.get(k)))},key,r)
                    else: disposition='matched'
                    output.append(p['id'])
                    if unit:
                        u=find_one('units',lambda u:u.get('property_id')==p['id'] and norm(u['name'])==norm(unit))
                        if not u:
                            u=save('units',{'name':unit,'property_id':p['id'],'market_rent':amount(r.get('Market rent'))/100,'deposit':amount(r.get('Deposit'))/100,'beds':clean(r.get('Beds')),'baths':clean(r.get('Baths')),'size':clean(r.get('Unit size')),'source_unit_type':clean(r.get('Unit type'))},key,r)
                        output.append(u['id'])
                elif kind=='tenants':
                    name=' '.join(clean(r.get(k)) for k in ('First name','Middle name','Last name') if clean(r.get(k)));email=clean(r.get('Primary email'))
                    t=find_one('tenants',lambda t:(norm(t.get('email'))==norm(email) if email else norm(t.get('name'))==norm(name)))
                    if t:disposition='matched'
                    else:
                        t=save('tenants',{'name':name,'source_display_name':' '.join(clean(r.get(k)) for k in ('First name','Last name') if clean(r.get(k))),'email':email,'phone':clean(r.get('Primary phone')),'address':', '.join(clean(r.get(k)) for k in ('Street address','Unit/Ap. #','City','State/Region','Zip','Country') if clean(r.get(k))),'status':'Prospective','notes':'Imported contact. Current/former status is not supplied by this export; review it.'},key,r)
                    output.append(t['id'])
                elif kind=='leases':
                    p=property_for(r);names=[n.strip() for n in clean(r.get('Tenant full name')).split(',') if n.strip()];emails=[n.strip() for n in clean(r.get('Tenant email')).split(',')]
                    if not names: raise ValueError('Lease residents are missing. Include the lease summary or its Residents worksheet.')
                    tenants=[tenant_for(n,emails[i] if i<len(emails) else '') for i,n in enumerate(names)]
                    if len(tenants)>2: raise ValueError('This lease has more than two tenants; preserved for review because Hearth currently supports two lease parties.')
                    status={'Active':'Active','Ended':'Ended','Past':'Ended','Scheduled':'Draft','Draft':'Draft'}.get(clean(r.get('Status')))
                    if not status: raise ValueError('Unrecognized lease status.')
                    data={'name':'Lease #'+clean(r.get('Lease #')),'property_id':p['id'],'tenant_id':tenants[0]['id'],'status':status,'term':clean(r.get('Lease type')),'start':iso(r.get('Start date')),'end':iso(r.get('End date')),'rent':amount(r.get('Rent amount'))/100,'recurring':False,'due_day':int(re.sub(r'\D','',clean(r.get('Rent due date'))) or '1'),'notes':'Imported lease. Automatic rent generation is OFF until rent shares, deposits, and first invoice date have been reviewed. Original details are retained below.'}
                    if len(tenants)>1:data.update(co_tenant_id=tenants[1]['id'],co_tenant_share=0,source_shares_unknown=True)
                    if clean(r.get('Unit #')):
                        u=find_one('units',lambda u:u.get('property_id')==p['id'] and norm(u['name'])==norm(r['Unit #']))
                        if not u:raise ValueError('Matching unit is missing.')
                        data['unit_id']=u['id']
                    l=save('leases',data,key,r);output.append(l['id'])
                    warnings.add('Imported leases have rent generation turned off: the export omits deposit terms and individual rent shares. Review before enabling it.')
                    if status=='Active':
                        for t in tenants:
                            if t.get('source_system')=='TenantCloud' and t.get('status')=='Prospective':store.write(con,'tenants',{**t,'status':'Current'},t['id'],t['version'])
                elif kind=='transactions':
                    if not clean(r.get('Transaction ID')): raise ValueError('Transaction ID is required for duplicate protection.')
                    typ=clean(r.get('Type')).split(' / ')[0];status=clean(r.get('Status'));total=amount(r.get('Total amount'));paid=amount(r.get('Paid amount'));left=amount(r.get('Left amount'))
                    if typ not in ('Income','Expense'):
                        disposition='preserved';counts['source_history']+=1
                        warnings.add('Credits and other unsupported accounting types are retained in Source history, excluded from cash totals. The export does not identify how credits were applied.')
                    else:
                        if status not in ('Paid','Partial','Open','Overdue','Void'):raise ValueError('Unrecognized transaction status.')
                        if status!='Void' and total!=paid+left:raise ValueError('Total, paid, and remaining amounts do not reconcile.')
                        if status=='Paid' and left:raise ValueError('Paid transaction has a remaining balance.')
                        p=property_for(r,required=typ=='Income');category=clean(r.get('Transaction category'));desc=clean(r.get('Transaction details')) or category
                        common={'property_id':p['id'] if p else '', 'date':iso(r.get('Due date')) or iso(r.get('Date created')),'category':category,'description':desc,'reference':clean(r['Transaction ID']),'void':status=='Void','notes':'Imported transaction summary. See original source values for full details.'}
                        if typ=='Expense':
                            for part,partamount in [('paid',paid),('unpaid',left)]:
                                if not partamount:continue
                                d={**common,'amount':partamount/100,'status':'Paid' if part=='paid' else 'Unpaid','due':common['date'],'payee':clean(r.get('Payer/payee')),'method':clean(r.get('Method of payment'))}
                                if part=='paid':
                                    d['paid_date']=iso(r.get('Date paid'))
                                    if not d['paid_date']:raise ValueError('Payment date is missing; cash timing cannot be inferred.')
                                output.append(save('expenses',d,key,r)['id'])
                        else:
                            t=tenant_for(r.get('Payer/payee'),r.get('Payer/payee email'));common['tenant_id']=t['id']
                            charge=save('charges',{**common,'amount':total/100},key,r);output.append(charge['id'])
                            if paid:
                                dt=iso(r.get('Date paid'))
                                if not dt:raise ValueError('Payment date is missing; cash timing cannot be inferred.')
                                payment=save('payments',{**common,'date':dt,'amount':paid/100,'charge_id':charge['id'],'method':clean(r.get('Method of payment')),'imported_summary':True},key,r);output.append(payment['id'])
                                warnings.add('Payment records are imported settlement summaries, not individual installments. Date paid is the export date field; installment timing and credit allocation are not available. No new receipts are issued for these summaries.')
                        scope='Income' if typ=='Income' else 'Expense'
                        if not find_one('categories',lambda c:c['name']==category and c['scope']==scope):save('categories',{'name':category,'scope':scope},'category:'+category,{})
                con.execute('INSERT OR REPLACE INTO transfer_sources VALUES(?,?,?,?,?,?,?)',(key,fingerprint,kind,json.dumps(r),json.dumps(output),disposition,batch_id))
                con.execute('RELEASE transfer_row')
                outcomes.append({'section':kind,'file':entry['file'],'row':entry['row'],'action':disposition,'label':clean(r.get('Property name') if kind=='properties' else r.get('First name') if kind=='tenants' else r.get('Lease #') if kind=='leases' else r.get('Transaction ID')),'ids':output})
                if disposition=='matched':counts['matched']+=1
            except (ValueError,TypeError,KeyError) as ex:
                con.execute('ROLLBACK TO transfer_row');con.execute('RELEASE transfer_row');counts=before
                issues.append({'file':entry['file'],'sheet':entry['sheet'],'row':entry['row'],'reason':str(ex)})
    return {'counts':dict(counts),'issues':issues,'warnings':sorted(warnings),'outcomes':outcomes}

def preview(store,files):
    tables,issues,inventory,attachments=parse_files(files)
    with store.lock,store.connect() as con:
        fingerprint=state_fingerprint(con)
        shadow=sqlite3.connect(':memory:');shadow.row_factory=sqlite3.Row
        try:
            con.backup(shadow);summary=run_import(store,shadow,tables,'preview')
        finally:shadow.close()
    present={t['kind'] for t in tables}
    included=set()
    for k in ('properties','tenants','leases'):
        if k in present or {'properties':'property_details','tenants':'tenant_details','leases':'lease_details'}[k] in present:included.add(k)
    if 'transactions' in present:included.add('transactions')
    if attachments:included.add('attachments')
    summary.update(inventory=inventory,included=[SECTIONS[k] for k in SECTIONS if k in included],missing=[SECTIONS[k] for k in SECTIONS if k not in included],adapter=VERSION,original_files=len(files))
    summary['issues']=issues+summary['issues']
    if attachments:summary['warnings'].append('Additional files are preserved inside the original archive. Automatic attachment association is not available for unverified layouts.')
    summary['warnings'].append('Missing sections do not block this import. They may be empty in the source account or omitted from your selection; Hearth cannot distinguish these cases.')
    summary['ready']=sum(v for k,v in summary['counts'].items() if k not in ('duplicates','matched'))
    return summary,fingerprint

def commit(store,files,fingerprint,summary):
    batch=uuid.uuid4().hex
    tables,_,_,_=parse_files(files)
    with store.lock,store.connect() as con:
        if state_fingerprint(con)!=fingerprint:raise ValueError('The workspace changed since the preview. Preview the files again before importing.')
        result=run_import(store,con,tables,batch)
        result={**summary,**result,'issues':summary['issues'],'warnings':summary['warnings'],'id':batch,'created':datetime.now().isoformat(timespec='seconds')}
        con.execute('INSERT INTO transfer_batches VALUES(?,?,?,?)',(batch,result['created'],'TenantCloud',json.dumps(result)))
        for name,content in files:
            con.execute('INSERT INTO transfer_originals VALUES(?,?,?,?,?)',(uuid.uuid4().hex,batch,name,content,hashlib.sha256(content).hexdigest()))
    return result

def history(store):
    with store.connect() as con:
        return [{**json.loads(r['summary']),'files':[{'id':f['id'],'name':f['name']} for f in con.execute('SELECT id,name FROM transfer_originals WHERE batch_id=?',(r['id'],))]} for r in con.execute('SELECT * FROM transfer_batches ORDER BY created DESC')]

def csv_bytes(headers,rows):
    out=io.StringIO();w=csv.writer(out);w.writerow(headers)
    for row in rows:
        values=[]
        for v in row:
            s=str(v if v is not None else '')
            # All data are values, never spreadsheet instructions.
            if (s.lstrip().startswith(('=','+','-','@')) and s.strip()!='-') or s.startswith(('\t','\r','\n')):s="'"+s
            values.append(s)
        w.writerow(values)
    return ('\ufeff'+out.getvalue()).encode('utf-8')

def export_tenantcloud(state,section,scope='all'):
    if scope not in ('all','active'): raise ValueError('Choose all records or active leases.')
    props={p['id']:p for p in state['properties']};tenants={t['id']:t for t in state['tenants']};units={u['id']:u for u in state['units']}
    rows=[];errors=[];warnings=[]
    def prop_values(p,u=None):
        r={**p,**(u or {})}
        return [p.get('name',''),u.get('name','') if u else '',p.get('address',''),p.get('city',''),p.get('region',''),p.get('postal',''),p.get('country',''),p.get('year',''),r.get('source_unit_type') or ('Apartment' if u else 'Single-Family'),r.get('size',''),r.get('beds',''),r.get('baths',''),r.get('market_rent',''),r.get('deposit','')]
    if section=='properties':
        headers=PROPERTY_TEMPLATE
        for p in props.values():
            us=[u for u in units.values() if u.get('property_id')==p['id']]
            if p.get('type')=='Multi unit' and not us: errors.append(p['name']+': add units before exporting a multi-unit property.');continue
            for u in us or [None]:rows.append(prop_values(p,u))
        for row in rows:
            if any(not clean(row[i]) for i in (0,2,3,4,5,6,8)):errors.append(str(row[0])+': address, city, state, postal code, country, and unit type are required by TenantCloud.')
    elif section=='tenants':
        headers=TENANT_TEMPLATE
        for t in tenants.values():
            raw=t.get('source_raw',{});parts=t['name'].split()
            # Use preserved structured fields only while the user has not renamed the tenant.
            same=norm(t['name'])==norm(' '.join(clean(raw.get(k)) for k in ('First name','Middle name','Last name') if clean(raw.get(k))))
            vals={k:clean(raw.get(k)) if same else '' for k in TENANT}
            vals.update({'First name':vals['First name'] or (parts[0] if parts else ''),'Last name':vals['Last name'] or (' '.join(parts[1:]) if len(parts)>1 else ''),'Primary email':t.get('email',''),'Primary phone':t.get('phone','')})
            for key in ('Primary phone','Additional phone'):
                if clean(vals[key]).startswith('+'): vals[key]=re.sub(r'[^0-9]','',vals[key])
            source_address=', '.join(clean(raw.get(k)) for k in ('Street address','Unit/Ap. #','City','State/Region','Zip','Country') if clean(raw.get(k)))
            if same and clean(t.get('address'))!=source_address:
                for key in ('Street address','Unit/Ap. #','City','State/Region','Zip','Country'):vals[key]=''
                warnings.append(t['name']+': edited free-text address cannot be split reliably; enter it in TenantCloud after import.')
            if t.get('address') and not same: warnings.append(t['name']+': free-text address retained in Hearth; enter structured address fields in TenantCloud after import.')
            if not vals['First name'] or not vals['Last name']:errors.append(t['name']+': TenantCloud requires first and last names.')
            rows.append([vals[k] for k in TENANT])
    elif section=='leases':
        headers=LEASE_TEMPLATE
        warnings.append('Lease CSVs can generate invoices in TenantCloud. Review its preview and invoicing options before submitting. This download does not import or invite anyone.')
        warnings.append('The TenantCloud lease template has no status column. Status is determined by its dates. Lease numbers, notes, custom fields, attachments and historical balances are not transferred by this template; use Hearth CSV/backup for a complete copy.')
        for l in state['leases']:
            if scope=='active' and l.get('status')!='Active':continue
            p=props.get(l.get('property_id'));t=tenants.get(l.get('tenant_id'));co=tenants.get(l.get('co_tenant_id'));u=units.get(l.get('unit_id'))
            if not p or not t:errors.append(l['name']+': missing property or tenant.');continue
            if l.get('status')=='Ended' and not l.get('end'):errors.append(l['name']+': ended lease has no end date. Add the actual end date before exporting so it cannot become an active lease.');continue
            if l.get('source_shares_unknown') and l.get('recurring'):errors.append(l['name']+': review individual rent shares before exporting invoicing.');continue
            pv=prop_values(p,u);start=l.get('start','');end=l.get('end','');rent=l.get('rent','') if l.get('recurring') else '';day=l.get('due_day',1)
            first=''
            if rent:
                import calendar
                d=date.fromisoformat(start);d=d.replace(day=min(int(day),calendar.monthrange(d.year,d.month)[1]))
                if d<date.fromisoformat(start):
                    y,m=(d.year+1,1) if d.month==12 else (d.year,d.month+1);d=date(y,m,min(int(day),calendar.monthrange(y,m)[1]))
                first=d.strftime('%m/%d/%Y')
            people=[t]+([co] if co else [])
            portions=', '.join(f'{v/100:.2f}' for v in [amount(l.get('rent'))-amount(l.get('co_tenant_share')),amount(l.get('co_tenant_share'))]) if co and rent else ''
            row=pv[:7]+[pv[8],', '.join(x['name'] for x in people),'',', '.join(x.get('email','') for x in people),'No',datetime.strptime(start,'%Y-%m-%d').strftime('%m/%d/%Y') if start else '',datetime.strptime(end,'%Y-%m-%d').strftime('%m/%d/%Y') if end else '','Tenants pay individually' if co and rent else 'Tenants pay jointly',rent,portions,first,'No','Monthly' if rent else '', '', '', '']
            if any(not clean(row[i]) for i in (0,2,3,4,5,6,7,8,12)):errors.append(l['name']+': required property or lease fields are missing.')
            if l.get('deposit'):warnings.append(l['name']+': deposit invoicing omitted because deposit allocation and invoice date need review.')
            if not l.get('recurring') and amount(l.get('rent')):warnings.append(l['name']+': recurring invoicing is disabled in Hearth. This template creates the lease without recurring rent invoices; the rent amount remains in Hearth and its native CSV.')
            rows.append(row)
    elif section=='transactions':
        headers=TRANSACTION
        warnings.append('Transaction CSV is an archive/report in TenantCloud export layout. TenantCloud has no verified self-service transaction importer; this file is not advertised as upload-ready.')
        seen=set()
        for kind in ('charges','expenses'):
            for r in state[kind]:
                raw=r.get('source_raw',{})
                if r.get('source_system')=='TenantCloud' and 'Transaction ID' in raw:
                    key=r['source_key']
                    if key not in seen:rows.append([raw.get(k,'') for k in TRANSACTION]);seen.add(key)
                    continue
                p=props.get(r.get('property_id'),{});t=tenants.get(r.get('tenant_id'),{})
                paid=sum(amount(a['amount']) for a in state['payments'] if a.get('charge_id')==r['id'] and not a.get('void')) if kind=='charges' else amount(r['amount']) if r.get('status')=='Paid' else 0
                total=amount(r['amount']);vals={'Transaction ID':r['id'],'Status':'Void' if r.get('void') else 'Paid' if total==paid else 'Partial' if paid else 'Open','Date created':r.get('created','')[:10],'Due date':r.get('date',''),'Date paid':r.get('paid_date',''),'Type':'Income / One Time' if kind=='charges' else 'Expense / One Time','Transaction category':r['category'],'Currency':'USD','Total amount':total/100,'Paid amount':paid/100,'Left amount':(total-paid)/100,'Method of payment':r.get('method',''),'Payer/payee':t.get('name',r.get('payee','')),'Payer/payee email':t.get('email',''),'Property name':p.get('name',''),'Street address':p.get('address',''),'City':p.get('city',''),'State/Region':p.get('region',''),'Zip':p.get('postal',''),'Country':p.get('country',''),'Transaction details':r.get('description','')}
                rows.append([vals.get(k,'') for k in headers])
    else: raise ValueError('Choose properties, tenants, leases, or transaction archive.')
    chunks=[rows[i:i+500] for i in range(0,len(rows),500)] or [[]]
    if section=='leases' and scope=='active':warnings.append('Only active leases are included. Ended and draft leases remain in Hearth.')
    return {'headers':headers,'rows':rows,'errors':sorted(set(errors)),'warnings':sorted(set(warnings)),'parts':len(chunks),'count':len(rows),'section':section,'scope':scope},chunks
