import base64
import io
import json
import sqlite3
import tempfile
import unittest
import zipfile
import threading
import secrets
import urllib.request
import urllib.error
from http.server import ThreadingHTTPServer
from datetime import date
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from server import Store, cents, Handler
from email_service import GoogleWorkspaceEmail
from restore_backup import restore

class DomainTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.s=Store(self.tmp.name)
        self.p=self.s.save('properties',{'name':'Test House','address':'123 Example','status':'Active'})
        self.t=self.s.save('tenants',{'name':'Test Tenant','status':'Current'})
    def tearDown(self):self.tmp.cleanup()
    def charge(self,amount=1000):return self.s.save('charges',{'property_id':self.p['id'],'tenant_id':self.t['id'],'date':'2026-09-01','amount':amount,'category':'Rent'})
    def payment(self,c,amount=400):return self.s.save('payments',{'property_id':self.p['id'],'tenant_id':self.t['id'],'charge_id':c['id'],'date':'2026-09-02','amount':amount,'category':'Rent','method':'Cash'})
    def test_partial_payment_and_overpayment(self):
        c=self.charge();self.payment(c)
        self.assertEqual(self.s.report({})['outstanding'][0]['balance'],600)
        with self.assertRaises(ValueError):self.payment(c,601)
        self.payment(c,600);self.assertEqual(self.s.report({})['outstanding'],[])
    def test_issued_receipt_is_immutable_and_void_preserves_history(self):
        c=self.charge();p=self.payment(c)
        with self.assertRaises(ValueError):self.s.save('payments',{**p,'amount':200},p['id'],p['version'])
        self.s.save('payments',{**p,'void':True},p['id'],p['version'])
        self.assertEqual(self.s.report({})['income'],0)
        self.assertEqual(len(self.s.state()['receipts']),1)
        self.assertEqual(self.s.report({})['outstanding'][0]['balance'],1000)
    def test_cannot_reduce_charge_below_payment_or_move_tenant(self):
        c=self.charge();self.payment(c)
        with self.assertRaises(ValueError):self.s.save('charges',{**c,'amount':100},c['id'],c['version'])
        with self.assertRaises(ValueError):self.s.save('charges',{**c,'void':True},c['id'],c['version'])
    def test_charge_matching_and_security_deposit_not_income(self):
        t2=self.s.save('tenants',{'name':'Other','status':'Current'});c=self.charge()
        with self.assertRaises(ValueError):self.s.save('payments',{'property_id':self.p['id'],'tenant_id':t2['id'],'charge_id':c['id'],'date':'2026-09-02','category':'Rent','amount':100})
        self.s.save('payments',{'property_id':self.p['id'],'tenant_id':self.t['id'],'date':'2026-09-02','category':'Security deposit','amount':500})
        report=self.s.report({});self.assertEqual(report['income'],0);self.assertEqual(report['deposits'],500)
    def test_rent_generation_is_idempotent_and_split_correctly(self):
        t2=self.s.save('tenants',{'name':'Second','status':'Current'})
        self.s.save('leases',{'name':'Test lease','property_id':self.p['id'],'tenant_id':self.t['id'],'co_tenant_id':t2['id'],'co_tenant_share':350,'rent':1000,'status':'Active','term':'Fixed','start':'2026-01-01','end':'2026-03-31','due_day':31,'recurring':True})
        self.assertEqual(self.s.generate_rent('2026-04-30')['created'],6)
        self.assertEqual(self.s.generate_rent('2026-04-30')['created'],0)
        rows=self.s.state()['charges'];self.assertEqual(sum(cents(r['amount']) for r in rows),300000)
        self.assertIn('2026-02-28',[r['date'] for r in rows])
    def test_expense_report_uses_cash_date_and_no_estimate_double_count(self):
        w=self.s.save('work',{'title':'Repair','property_id':self.p['id'],'category':'Plumbing','status':'Open','estimate':900})
        self.s.save('expenses',{'description':'Parts','date':'2026-08-29','paid_date':'2026-09-01','status':'Paid','category':'Plumbing','amount':100.15,'property_id':self.p['id'],'work_id':w['id']})
        self.s.save('expenses',{'description':'Labor','date':'2026-09-02','status':'Unpaid','category':'Plumbing','amount':200,'property_id':self.p['id'],'work_id':w['id']})
        report=self.s.report({'start':'2026-09-01','end':'2026-09-30'});self.assertEqual(report['expenses'],100.15);self.assertEqual(report['categories'][0]['amount'],100.15)
    def test_required_custom_fields_and_choice_validation(self):
        f=self.s.save('fields',{'name':'Warranty','entity':'work','field_type':'Choice','options':'Yes,No','required':True})
        data={'title':'Repair','property_id':self.p['id'],'category':'Plumbing','status':'Open'}
        with self.assertRaises(ValueError):self.s.save('work',data)
        with self.assertRaises(ValueError):self.s.save('work',{**data,'custom':{f['id']:'Maybe'}})
        self.s.save('work',{**data,'custom':{f['id']:'Yes'}})
    def test_revision_conflict_and_linked_archive_protection(self):
        p=self.s.save('properties',{**self.p,'name':'Renamed'},self.p['id'],self.p['version'])
        with self.assertRaises(ValueError):self.s.save('properties',self.p,self.p['id'],self.p['version'])
        c=self.charge()
        with self.assertRaises(ValueError):self.s.archive(self.p['id'])
        with self.assertRaises(ValueError):self.s.archive(c['id'])
    def test_backup_has_consistent_database_and_attachment(self):
        f=self.s.add_file({'name':'receipt.txt','record_id':self.p['id'],'content':base64.b64encode(b'test receipt').decode()})
        data=self.s.backup()
        with zipfile.ZipFile(io.BytesIO(data)) as z:
            self.assertEqual(z.read('uploads/'+f['id']),b'test receipt')
            self.assertIn('hearth.sqlite3',z.namelist());self.assertEqual(json.loads(z.read('manifest.json'))['format'],1)
    def test_money_precision_validation(self):
        self.assertEqual(cents('0.29'),29)
        for val in ('nan','Infinity','-1','1.001','abc'):
            with self.assertRaises(ValueError):cents(val)
    def test_due_day_change_does_not_duplicate_same_month(self):
        l=self.s.save('leases',{'name':'Monthly','property_id':self.p['id'],'tenant_id':self.t['id'],'rent':1000,'status':'Active','term':'Month-to-month','start':'2026-01-01','due_day':1,'recurring':True})
        self.assertEqual(self.s.generate_rent('2026-01-31')['created'],1)
        self.s.save('leases',{**l,'due_day':15},l['id'],l['version'])
        self.assertEqual(self.s.generate_rent('2026-01-31')['created'],0)
    def test_restore_round_trip_keeps_files(self):
        f=self.s.add_file({'name':'receipt.txt','record_id':self.p['id'],'content':base64.b64encode(b'backup round trip').decode()})
        source=Path(self.tmp.name)/'backup.zip';source.write_bytes(self.s.backup())
        dest=Path(self.tmp.name)/'restored';restore(source,dest)
        reopened=Store(dest)
        self.assertEqual(reopened.state()['properties'][0]['name'],'Test House')
        self.assertEqual((dest/'uploads'/f['id']).read_bytes(),b'backup round trip')
        with self.assertRaises(ValueError):restore(source,dest)
    def test_linked_work_cannot_move_to_wrong_property(self):
        w=self.s.save('work',{'title':'Repair','property_id':self.p['id'],'category':'Plumbing','status':'Open'})
        self.s.save('expenses',{'description':'Parts','date':'2026-09-01','status':'Paid','category':'Plumbing','amount':100,'property_id':self.p['id'],'work_id':w['id']})
        other=self.s.save('properties',{'name':'Other House','address':'234 Example','status':'Active'})
        with self.assertRaises(ValueError):self.s.save('work',{**w,'property_id':other['id']},w['id'],w['version'])

class HTTPTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.server=ThreadingHTTPServer(('127.0.0.1',0),Handler)
        self.server.store=Store(self.tmp.name);self.server.email_service=GoogleWorkspaceEmail(self.tmp.name);self.server.token=secrets.token_urlsafe();self.server.demo=True;self.server.public=False;self.server.base_url=''
        self.thread=threading.Thread(target=self.server.serve_forever,daemon=True);self.thread.start()
        self.url=f'http://127.0.0.1:{self.server.server_port}'
    def tearDown(self):self.server.shutdown();self.server.server_close();self.thread.join();self.tmp.cleanup()
    def test_protects_writes_and_reads_from_foreign_origins(self):
        req=urllib.request.Request(self.url+'/api/save',data=b'{}',headers={'Content-Type':'application/json'})
        with self.assertRaises(urllib.error.HTTPError) as err:urllib.request.urlopen(req)
        self.assertEqual(err.exception.code,403)
    def test_public_mode_requires_basic_auth_and_same_origin(self):
        self.server.public=True;self.server.auth_username='owner';self.server.auth_password='long-test-password';self.server.base_url='https://hearth.example'
        with self.assertRaises(urllib.error.HTTPError) as err:urllib.request.urlopen(self.url+'/api/state')
        self.assertEqual(err.exception.code,401)
        auth=base64.b64encode(b'owner:long-test-password').decode()
        req=urllib.request.Request(self.url+'/api/state',headers={'Authorization':'Basic '+auth,'Host':f'127.0.0.1:{self.server.server_port}'})
        with urllib.request.urlopen(req) as response:self.assertEqual(response.status,200)
        req=urllib.request.Request(self.url+'/api/state',headers={'Authorization':'Basic '+auth,'Origin':'https://unrelated.example'})
        with self.assertRaises(urllib.error.HTTPError) as err:urllib.request.urlopen(req)
        self.assertEqual(err.exception.code,403)
    def test_imported_payment_receipt_is_created_once_and_locked(self):
        p=self.server.store.save('properties',{'name':'Test House','address':'123 Example','status':'Active'})
        t=self.server.store.save('tenants',{'name':'Test Tenant','status':'Current'})
        payment=self.server.store.save('payments',{'property_id':p['id'],'tenant_id':t['id'],'date':'2026-09-02','amount':900,'category':'Rent','method':'Venmo','imported_summary':True})
        receipt=self.server.store.create_receipt(payment['id'])
        with self.assertRaisesRegex(ValueError,'already has a locked receipt'):self.server.store.create_receipt(payment['id'])
        with urllib.request.urlopen(self.url+f'/receipt/{receipt["number"]}') as response:
            page=response.read().decode()
        self.assertIn('Payment receipt',page);self.assertIn('Test Tenant',page);self.assertIn('$900.00',page)
        req=urllib.request.Request(self.url+'/api/state',headers={'Origin':'https://unrelated.example'})
        with self.assertRaises(urllib.error.HTTPError) as err:urllib.request.urlopen(req)
        self.assertEqual(err.exception.code,403)
    def test_http_upload_and_download_round_trip(self):
        payload=json.dumps({'name':'receipt.txt','content':base64.b64encode(b'sample receipt').decode()}).encode()
        req=urllib.request.Request(self.url+'/api/upload',data=payload,headers={'Content-Type':'application/json','X-Hearth-Token':self.server.token})
        with urllib.request.urlopen(req) as r:fid=json.load(r)['id']
        with urllib.request.urlopen(self.url+'/api/files/'+fid) as r:
            self.assertEqual(r.read(),b'sample receipt');self.assertIn('attachment',r.headers['Content-Disposition'])
    def test_import_is_atomic_when_row_invalid(self):
        payload=json.dumps({'kind':'properties','rows':[{'name':'Valid','address':'1 Test','status':'Active'},{'name':'Invalid'}]}).encode()
        req=urllib.request.Request(self.url+'/api/import',data=payload,headers={'Content-Type':'application/json','X-Hearth-Token':self.server.token})
        with self.assertRaises(urllib.error.HTTPError):urllib.request.urlopen(req)
        self.assertEqual(self.server.store.state()['properties'],[])

if __name__=='__main__':unittest.main()
