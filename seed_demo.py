"""Create a separate sample workspace. Never touches the real data directory."""
import base64
import json
import calendar
from datetime import date
from pathlib import Path
from server import Store

def seed():
    store=Store(Path(__file__).parent/'demo-data')
    if store.state()['properties']:
        print('Sample workspace already exists; preserved existing preview changes.')
        return
    current=date.today(); month=current.isoformat()[:7]
    d=lambda day:f'{month}-{min(day,calendar.monthrange(current.year,current.month)[1]):02}'
    p1=store.save('properties',{'name':'Willow House','address':'128 Willow Lane','city':'Sample City','region':'CA','postal':'90000','country':'US','type':'Single family','status':'Active','beds':3,'baths':2,'size':1640,'year':1998,'market_rent':2400,'deposit':2400,'amenities':'Fenced yard, two-car garage, central air','utilities':'Tenant: electricity and gas. Owner: water, sewer, trash.','notes':'Fictional sample property for the interactive preview.'})
    p2=store.save('properties',{'name':'Cedar Cottage','address':'42 Cedar Court','city':'Sample City','region':'CA','postal':'90000','country':'US','type':'Single family','status':'Active','beds':2,'baths':1,'size':1120,'year':1976,'market_rent':1850,'deposit':1850,'amenities':'Covered patio, laundry, garden','notes':'Fictional sample property for the interactive preview.'})
    t1=store.save('tenants',{'name':'Alex Morgan','email':'alex@example.com','phone':'555-0101','status':'Current','notes':'Sample tenant — no messages are sent.'})
    t2=store.save('tenants',{'name':'Sam Rivera','email':'sam@example.com','phone':'555-0102','status':'Current','pets':'One indoor cat','notes':'Sample tenant — no messages are sent.'})
    v1=store.save('vendors',{'name':'Clearwater Plumbing','contact':'Jordan Lee','trade':'Plumbing','email':'service@example.com','phone':'555-0110'})
    v2=store.save('vendors',{'name':'Evergreen Home Care','trade':'Landscaping & general repair','email':'care@example.com','phone':'555-0111'})
    for p,t,r in [(p1,t1,2400),(p2,t2,1850)]:
        store.save('leases',{'name':p['name']+' · '+str(current.year),'property_id':p['id'],'tenant_id':t['id'],'start':d(1),'end':f'{current.year+1}-{current.month:02}-01','status':'Active','term':'Fixed','rent':r,'deposit':r,'due_day':1,'recurring':True,'grace_days':5,'notes':'Sample management record. Attach your signed agreement in a real workspace.'})
    store.generate_rent(current.isoformat())
    charges=store.state()['charges']
    for c in charges:
        store.save('payments',{'property_id':c['property_id'],'tenant_id':c['tenant_id'],'charge_id':c['id'],'date':d(1),'category':'Rent','amount':c['amount'] if c['tenant_id']==t1['id'] else 1500,'method':'Bank transfer','reference':'DEMO-RENT','description':'Monthly rent — sample payment'})
    works=[]
    for title,p,category,status,estimate,v,due in [('Replace kitchen faucet',p1,'Plumbing','Completed',500,v1,8),('Refresh garden beds',p2,'Landscaping','In progress',650,v2,28),('Inspect hallway outlet',p1,'Electrical','Open',225,None,30),('Autumn HVAC service',p2,'HVAC','Scheduled',180,None,30)]:
        works.append(store.save('work',{'title':title,'property_id':p['id'],'category':category,'status':status,'priority':'High' if category=='Electrical' else 'Normal','date':d(3),'due':d(due),'estimate':estimate,'vendor_id':v['id'] if v else '', 'description':'Sample work order. Open it to review costs, documents, and status.','entry':'Arrange access with tenant before visiting.'}))
    expenses=[]
    for title,p,cat,amount,status,day,work,v,ctype in [('Kitchen faucet and fittings',p1,'Plumbing',168.75,'Paid',5,works[0],v1,'Materials'),('Faucet installation labor',p1,'Plumbing',240,'Paid',8,works[0],v1,'Labor'),('Mulch and plants',p2,'Landscaping',214.50,'Paid',12,works[1],v2,'Materials'),('Garden preparation',p2,'Landscaping',275,'Unpaid',20,works[1],v2,'Labor'),('Water and sewer',p1,'Utilities',96.20,'Paid',16,None,None,'Service')]:
        expenses.append(store.save('expenses',{'description':title,'property_id':p['id'],'category':cat,'amount':amount,'status':status,'date':d(day),'paid_date':d(day) if status=='Paid' else '', 'work_id':work['id'] if work else '', 'vendor_id':v['id'] if v else '', 'payee':v['name'] if v else 'Sample utility company','cost_type':ctype,'reference':'SAMPLE-'+str(day)}))
    receipt=b'Hearth sample receipt\nFictional receipt for preview only.\nKitchen faucet and fittings: $168.75\nPaid by card.\n'
    store.add_file({'name':'sample-faucet-receipt.txt','record_id':expenses[0]['id'],'content':base64.b64encode(receipt).decode()})
    field=store.save('fields',{'name':'Warranty expires','entity':'work','field_type':'Date','required':False})
    w=works[0];store.save('work',{**w,'custom':{field['id']:f'{current.year+2}-09-30'}},w['id'],w['version'])
    store.save('tasks',{'title':'Review insurance renewal','date':d(30),'status':'To do','property_id':p1['id'],'notes':'Sample reminder.'})
    store.save('inspections',{'title':'Fall condition review','property_id':p2['id'],'date':d(30),'status':'Scheduled','inspection_type':'Routine','checklist':'Kitchen: check under-sink cabinet.\nLiving room: inspect paint and flooring.\nExterior: inspect gutters and drainage.'})
    with store.connect() as con:
        con.execute("UPDATE settings SET value=? WHERE key='owner'",(json.dumps({'name':'Demo Owner','business':'Hearth · Sample Workspace','email':'owner@example.com','address':'Fictional preview records','currency':'USD'}),))
    print('Sample workspace created in demo-data. Real workspace remains unchanged.')

if __name__=='__main__':seed()
