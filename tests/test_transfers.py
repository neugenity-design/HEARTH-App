import csv
import io
import json
from pathlib import Path
import sqlite3
import sys
import tempfile
import unittest
import zipfile

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from server import Store
import transfers as tr

P=dict(zip(tr.PROPERTY,['Oak House','','10 Test Street','Sample City','CA','00123','US','2001','Single-Family','1400','3','2','1500','1000']))
T=dict(zip(tr.TENANT,['Robin','','Tester','','','robin@example.com','','555-0100','','','','','','','']))
L=dict(zip(tr.LEASE,['1','Active','Month-to-month','Sep 1, 2026','Sep 1, 2026','-','Robin Tester','robin@example.com','-','USD','1500','Monthly','1st','Sep 1, 2026','Oak House','-','10 Test Street','Sample City','CA','00123','US']))
X=dict(zip(tr.TRANSACTION,['9001','Partial','Sep 1, 2026','Sep 1, 2026','Sep 15, 2026','Income / One Time','Rent','USD','1500','500','1000','Venmo','Robin Tester','robin@example.com','1','Oak House','-','10 Test Street','Sample City','CA','00123','US','Rent','']))

def file(headers,rows,name='data.csv'):
    out=io.StringIO();w=csv.writer(out);w.writerow(headers)
    for r in rows:w.writerow([r.get(h,'') for h in headers])
    return name,out.getvalue().encode()

def package():return [file(tr.PROPERTY,[P],'properties.csv'),file(tr.TENANT,[T],'tenants.csv'),file(tr.LEASE,[L],'leases.csv'),file(tr.TRANSACTION,[X],'transactions.csv')]

class TransferTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.store=Store(self.temp.name)
    def tearDown(self):self.temp.cleanup()
    def run_import(self,files):
        p,f=tr.preview(self.store,files);return tr.commit(self.store,files,f,p)
    def test_preview_does_not_save_and_commit_routes_relationships(self):
        p,f=tr.preview(self.store,package())
        self.assertFalse(self.store.state()['properties']);self.assertEqual(p['counts']['payments'],1)
        result=tr.commit(self.store,package(),f,p);s=self.store.state()
        self.assertFalse(result['issues']);self.assertEqual(s['properties'][0]['postal'],'00123')
        self.assertEqual(s['payments'][0]['charge_id'],s['charges'][0]['id']);self.assertEqual(s['leases'][0]['tenant_id'],s['tenants'][0]['id'])
        self.assertFalse(s['receipts']);self.assertFalse(s['leases'][0]['recurring'])
        self.assertEqual(self.store.report({})['outstanding'][0]['balance'],1000)
    def test_partial_files_warn_but_import(self):
        r=self.run_import([file(tr.TENANT,[T])]);self.assertEqual(r['counts']['tenants'],1)
        self.assertIn('Properties & units',r['missing']);self.assertFalse(r['issues'])
    def test_detail_only_property_is_labeled_as_included(self):
        r=self.run_import([file(tr.PROPERTY_DETAIL,[{**P,'Currency':'USD'}])])
        self.assertIn('Properties & units',r['included']);self.assertNotIn('Properties & units',r['missing'])
    def test_reordered_lease_parties_do_not_create_another_lease(self):
        t2={**T,'First name':'Jamie','Primary email':'jamie@example.com'}
        lease={**L,'Tenant full name':'Robin Tester, Jamie Tester','Tenant email':'robin@example.com, jamie@example.com'}
        self.run_import([file(tr.PROPERTY,[P]),file(tr.TENANT,[T,t2]),file(tr.LEASE,[lease])])
        reversed_lease={**lease,'Tenant full name':'Jamie Tester, Robin Tester','Tenant email':'jamie@example.com, robin@example.com'}
        r=self.run_import([file(tr.LEASE,[reversed_lease])])
        self.assertEqual(len(self.store.state()['leases']),1);self.assertEqual(len(r['issues']),1)
    def test_missing_dependencies_do_not_block_independent_rows(self):
        files=[file(tr.TENANT,[T]),file(tr.TRANSACTION,[X],'invoices.csv')]
        r=self.run_import(files);self.assertEqual(r['counts']['tenants'],1);self.assertEqual(len(r['issues']),1)
        self.assertFalse(self.store.state()['charges'])
        self.run_import([file(tr.PROPERTY,[P])]);r=self.run_import(files)
        self.assertEqual(r['counts']['duplicates'],1);self.assertEqual(r['counts']['charges'],1)
    def test_duplicate_and_changed_source_never_overwrite(self):
        self.run_import(package());r=self.run_import(package());self.assertEqual(r['counts'],{'duplicates':4})
        changed=[file(tr.TRANSACTION,[{**X,'Total amount':'1600','Left amount':'1100'}])]
        r=self.run_import(changed);self.assertEqual(len(r['issues']),1);self.assertEqual(self.store.state()['charges'][0]['amount'],1500)
    def test_incorrect_application_and_duplicate_headers_rejected(self):
        for content in (b'name,address\nOther App,Example\n',b'Property name,Property name\nA,B\n',b'id,amount\n1,9\n'):
            with self.assertRaisesRegex(ValueError,'correct TenantCloud format'):tr.preview(self.store,[('TenantCloud.csv',content)])
    def test_partial_expense_does_not_overstate_cash(self):
        expense={**X,'Type':'Expense / One Time','Transaction category':'Repairs','Payer/payee':'Test Plumber','Property name':'-','Street address':'-'}
        r=self.run_import([file(tr.TRANSACTION,[expense])]);s=self.store.state()
        self.assertFalse(r['issues']);self.assertEqual(len(s['expenses']),2)
        self.assertEqual(sum(x['amount'] for x in s['expenses']),1500);self.assertEqual(self.store.report({})['expenses'],500)
    def test_credits_preserved_without_inflating_cash(self):
        credit={**X,'Type':'Credits / One Time','Status':'Paid','Total amount':'50','Paid amount':'50','Left amount':'0'}
        r=self.run_import([file(tr.TRANSACTION,[credit])]);self.assertEqual(r['counts']['source_history'],1)
        self.assertFalse(self.store.state()['payments']);self.assertEqual(self.store.report({})['income'],0)
        with self.store.connect() as c:self.assertEqual(json.loads(c.execute('SELECT raw FROM transfer_sources').fetchone()[0])['Total amount'],'50')
    def test_stale_preview_rejected(self):
        p,f=tr.preview(self.store,package());self.store.save('tenants',{'name':'New Person','status':'Prospective'})
        with self.assertRaisesRegex(ValueError,'workspace changed'):tr.commit(self.store,package(),f,p)
        self.assertFalse(self.store.state()['properties'])
    def test_unexpected_failure_rolls_back_entire_batch(self):
        p,f=tr.preview(self.store,package());write=self.store.write
        def fail(con,kind,*args,**kwargs):
            if kind=='payments':raise RuntimeError('disk fault')
            return write(con,kind,*args,**kwargs)
        self.store.write=fail
        with self.assertRaises(RuntimeError):tr.commit(self.store,package(),f,p)
        self.assertFalse(self.store.state()['properties']);self.assertFalse(tr.history(self.store))
    def test_bad_row_kept_out_while_valid_row_imports(self):
        bad={**X,'Transaction ID':'9002','Paid amount':'600'}
        files=package()[:-1]+[file(tr.TRANSACTION,[X,bad])]
        r=self.run_import(files);self.assertEqual(len(r['issues']),1);self.assertEqual(len(self.store.state()['charges']),1)
    def test_safe_archive_handling(self):
        buf=io.BytesIO()
        with zipfile.ZipFile(buf,'w') as z:z.writestr('../escape.csv',file(tr.PROPERTY,[P])[1])
        with self.assertRaisesRegex(ValueError,'Unsafe'):tr.preview(self.store,[('export.zip',buf.getvalue())])
    def test_original_files_retained_byte_for_byte_and_in_backup(self):
        files=package();r=self.run_import(files)
        with self.store.connect() as c:
            originals=[(x['name'],x['content']) for x in c.execute('SELECT name,content FROM transfer_originals')]
        self.assertEqual(originals,files)
        with zipfile.ZipFile(io.BytesIO(self.store.backup())) as z:self.assertIsNone(z.testzip())
    def test_export_headers_and_missing_fields(self):
        self.run_import(package());state=self.store.state()
        for section,headers in [('properties',tr.PROPERTY_TEMPLATE),('tenants',tr.TENANT_TEMPLATE),('leases',tr.LEASE_TEMPLATE)]:
            result,chunks=tr.export_tenantcloud(state,section);self.assertEqual(result['headers'],headers);self.assertFalse(result['errors'])
            self.assertTrue(all(len(r)==len(headers) for r in result['rows']))
        state['properties'][0]['postal']='';r,_=tr.export_tenantcloud(state,'properties');self.assertTrue(r['errors'])
    def test_export_chunks_at_tenantcloud_limit_and_csv_escaping(self):
        s=self.store.state();s['tenants']=[{'id':str(i),'name':'Test Person','email':f'test{i}@example.com'} for i in range(501)]
        r,chunks=tr.export_tenantcloud(s,'tenants');self.assertEqual([len(c) for c in chunks],[500,1])
        rows=list(csv.reader(io.StringIO(tr.csv_bytes(['Text'],[['=1+1'],['line one\nline two'],['a,b']]).decode('utf-8-sig'))))
        self.assertEqual(rows[1],["'=1+1"]);self.assertEqual(rows[2],['line one\nline two']);self.assertEqual(rows[3],['a,b'])
    def test_photo_must_belong_to_property(self):
        p=self.store.save('properties',{'name':'Photo House','address':'1 Test','status':'Active'})
        with self.assertRaisesRegex(ValueError,'image attached'):self.store.save('properties',{**p,'photo_id':'missing'},p['id'],p['version'])
    def test_ended_lease_without_end_date_cannot_export_as_active(self):
        self.run_import(package());s=self.store.state();s['leases'][0]['status']='Ended'
        result,_=tr.export_tenantcloud(s,'leases');self.assertTrue(result['errors'])
        result,_=tr.export_tenantcloud(s,'leases','active');self.assertEqual(result['count'],0)
    def test_xlsx_reader_and_zip_multifile_import(self):
        from xml.sax.saxutils import escape
        def workbook(headers,row):
            out=io.BytesIO()
            with zipfile.ZipFile(out,'w') as z:
                z.writestr('xl/workbook.xml','<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets><sheet name="Data" sheetId="1" r:id="rId1"/></sheets></workbook>')
                z.writestr('xl/_rels/workbook.xml.rels','<Relationships><Relationship Id="rId1" Target="worksheets/sheet1.xml"/></Relationships>')
                rows=''
                for i,values in enumerate([headers,[row.get(k,'') for k in headers]],1):
                    rows+='<row>'+''.join(f'<c r="{chr(65+j)}{i}" t="inlineStr"><is><t>{escape(str(v))}</t></is></c>' for j,v in enumerate(values))+'</row>'
                z.writestr('xl/worksheets/sheet1.xml','<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData>'+rows+'</sheetData></worksheet>')
            return out.getvalue()
        out=io.BytesIO()
        with zipfile.ZipFile(out,'w') as z:
            z.writestr('Properties/Properties.xlsx',workbook(tr.PROPERTY,P))
            z.writestr('Tenants/Tenants.xlsx',workbook(tr.TENANT,T))
        result=self.run_import([('export.zip',out.getvalue())]);self.assertFalse(result['issues'])
        self.assertEqual(result['counts']['properties'],1);self.assertEqual(result['counts']['tenants'],1)

if __name__=='__main__':unittest.main()
