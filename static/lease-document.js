import {californiaTemplate} from './lease-templates.js';
import {escapeHTML as esc} from './controls.js';

export const sectionTypes = [['text','Terms / text'],['details','Details'],['charges','Rent & charges'],['signature','Signatures']];
const money = n => new Intl.NumberFormat('en-US',{style:'currency',currency:'USD'}).format(Number(n)||0);
const date = s => s ? new Date(s+'T12:00:00').toLocaleDateString('en-US',{month:'long',day:'numeric',year:'numeric'}) : '';
export const fillTokens = (text,context) => String(text??'').replace(/\{\{(\w+)\}\}/g,(token,key)=>context[key]!==undefined&&context[key]!==''?context[key]:token);

export function leaseContext(lease,state) {
  const get = (kind,id) => (state[kind]||[]).find(r=>r.id===id)||{};
  const property=get('properties',lease.property_id), tenant=get('tenants',lease.tenant_id), co=get('tenants',lease.co_tenant_id), unit=get('units',lease.unit_id);
  return {owner_name:state.owner?.business||state.owner?.name||'',owner_address:state.owner?.address||'',tenant_name:tenant.name||'',co_tenant_name:co.name||'',tenant_names:[tenant.name,co.name].filter(Boolean).join(' and '),property_type:property.type||'residential property',occupant_names:[tenant.name,co.name,tenant.occupants,co.occupants].filter(Boolean).join(', '),payment_methods:'ACH; Credit/Debit card; Cash; Other',tenant_utilities:'Cable & Communication Services, Cable/Satellite, Electrical Services, Gas Services, Internet, Laundry Services, Phone',landlord_utilities:'City Services, Garbage Service, Government, Landscaping, Pest Control, Sewer, Water',notice_days:'30',governing_state:property.region||'California',term_end_statement:lease.term==='Month-to-month'?'The lease continues on a month-to-month basis.':'The lease will end on '+date(lease.end)+'.',property_name:property.name||'',property_address:[property.address,property.city,property.region,property.postal].filter(Boolean).join(', '),unit_name:unit.name||'',lease_name:lease.name,start_date:date(lease.start),end_date:lease.term==='Month-to-month'?'Month-to-month':date(lease.end),lease_term:lease.term,monthly_rent:money(lease.rent),due_day:String(lease.due_day||1),security_deposit:money(lease.deposit),late_fee:money(lease.late_fee),grace_days:String(lease.grace_days||0),utilities:lease.utilities||property.utilities||''};
}

export function newSection(type='text',id=crypto.randomUUID()) {
  return {id,type,title:sectionTypes.find(item=>item[0]===type)?.[1]||'Additional terms',body:'',enabled:true,rows:['details','charges'].includes(type)?[{label:'',value:''}]:[]};
}

export function createLeaseDocument(lease,state,templateId='california-owner-v1') {
  const context=leaseContext(lease,state);
  if(templateId===californiaTemplate.id)return {schemaVersion:1,revision:0,templateId:californiaTemplate.id,templateVersion:californiaTemplate.version,templateName:californiaTemplate.name,title:'Residential lease agreement',subtitle:lease.name,introduction:'This agreement, dated {{start_date}}, is between {{owner_name}} and {{tenant_names}}.',context:{...context,governing_state:'California'},sections:californiaTemplate.sections.map(([title,body])=>({...newSection('text'),title,body}))};
  return {schemaVersion:1,revision:0,templateId:'basic',templateName:'Basic lease outline',title:'Residential lease agreement',subtitle:lease.name,context,sections:[
    {...newSection('details'),title:'Parties',rows:[{label:'Landlord / owner',value:'{{owner_name}}'},{label:'Tenant(s)',value:'{{tenant_names}}'}]},
    {...newSection('details'),title:'Premises',rows:[{label:'Property',value:'{{property_name}}'},{label:'Address',value:'{{property_address}}'},...(context.unit_name?[{label:'Unit',value:'{{unit_name}}'}]:[])]},
    {...newSection('details'),title:'Lease term',rows:[{label:'Term',value:'{{lease_term}}'},{label:'Start date',value:'{{start_date}}'},{label:'End date / continuation',value:'{{end_date}}'}]},
    {...newSection('charges'),title:'Rent, deposit & fees',rows:[{label:'Monthly rent',value:'{{monthly_rent}}'},{label:'Rent due day of each month',value:'{{due_day}}'},{label:'Security deposit',value:'{{security_deposit}}'},{label:'Agreed late fee',value:'{{late_fee}}'},{label:'Grace period (days)',value:'{{grace_days}}'}]},
    {...newSection('text'),title:'Utility responsibilities',body:context.utilities?'{{utilities}}':'',enabled:!!context.utilities},
    {...newSection('text'),title:'Additional lease terms',body:'',enabled:false},
    {...newSection('signature'),title:'Signatures',body:'Landlord / owner: {{owner_name}}\nTenant(s): {{tenant_names}}'}
  ]};
}

export function documentIssues(doc) {
  const issues=[];
  if(/\{\{\w+\}\}/.test(fillTokens(doc.introduction,doc.context)))issues.push('Fill the missing information in the introduction.');
  if (!doc.title?.trim()) issues.push('Enter a document title.');
  const sections=doc.sections.filter(s=>s.enabled!==false);
  if (!sections.length) issues.push('Include at least one section.');
  for (const section of sections) {
    if (!section.title?.trim()) issues.push('Every included section needs a title.');
    const texts=[section.title,section.body,...(section.rows||[]).flatMap(row=>[row.label,row.value])];
    if (section.type==='text'&&!section.body?.trim()) issues.push(`Add text to “${section.title}” or exclude it.`);
    if (['details','charges'].includes(section.type)&&(!section.rows?.length||section.rows.some(row=>!row.label.trim()||!row.value.trim()))) issues.push(`Complete the rows in “${section.title}”.`);
    if (texts.some(text=>/\{\{\w+\}\}/.test(fillTokens(text,doc.context)))) issues.push(`Fill the missing lease information in “${section.title}”.`);
  }
  return [...new Set(issues)];
}

export function moveSection(sections,id,offset) {
  const result=[...sections],index=result.findIndex(s=>s.id===id),next=index+offset;
  if(index<0||next<0||next>=result.length)return result;
  [result[index],result[next]]=[result[next],result[index]];
  return result;
}

// Review and generated/printed documents use this same escaped HTML renderer.
export function renderLeaseBody(doc) {
  const fill=text=>esc(fillTokens(text,doc.context));
  return `<article class="lease-paper"><header><p class="document-label">Lease document · Draft / unsigned</p><h1>${fill(doc.title)}</h1><p>${fill(doc.subtitle)}</p></header>${doc.introduction?`<p class="lease-prose">${fill(doc.introduction)}</p>`:''}${doc.sections.filter(s=>s.enabled!==false).map((section,index)=>`<section class="lease-clause"><h2>${index+1}. ${fill(section.title)}</h2>${section.body?`<p class="lease-prose">${fill(section.body)}</p>`:''}${['details','charges'].includes(section.type)?`<dl class="lease-terms">${section.rows.map(row=>`<div><dt>${fill(row.label)}</dt><dd>${fill(row.value)}</dd></div>`).join('')}</dl>`:''}${section.type==='signature'?`<div class="signature-lines">${[doc.context.owner_name,...[doc.context.tenant_name,doc.context.co_tenant_name].filter(Boolean)].map(name=>`<div><p>${esc(name||'Name')}</p><p>Signature: __________________________</p><p>Date: ______________________________</p></div>`).join('')}</div>`:''}</section>`).join('')}<footer>Draft / unsigned · Revision ${Number(doc.revision)||0}</footer></article>`;
}

export const documentStyles=`body{margin:0;background:#fff;color:#263c34;font:14px/1.6 Arial,Helvetica,sans-serif}.lease-paper{max-width:800px;margin:auto;padding:46px}.lease-paper header{border-bottom:2px solid #24493b;padding-bottom:22px;margin-bottom:30px}.lease-paper h1{font:32px Georgia,serif}.document-label{font-size:11px;text-transform:uppercase;letter-spacing:2px;color:#768078}.lease-clause{margin:25px 0}.lease-clause h2{font-size:17px;border-bottom:1px solid #dce1d6;padding-bottom:9px;break-after:avoid}.lease-prose{white-space:pre-wrap;overflow-wrap:anywhere}.lease-terms{margin:12px 0}.lease-terms>div{display:grid;grid-template-columns:1fr 1.4fr;gap:20px;border-bottom:1px solid #e3e7de;padding:10px 0;break-inside:avoid}.lease-terms dt{font-weight:600}.lease-terms dd{margin:0;white-space:pre-wrap;overflow-wrap:anywhere}.signature-lines{display:flex;flex-wrap:wrap;gap:24px;break-inside:avoid}.signature-lines>div{flex:1;min-width:210px}.lease-paper footer{margin-top:35px;border-top:1px solid #ddd;padding-top:12px;font-size:10px;color:#768078}@page{size:letter;margin:18mm}@media print{.lease-paper{padding:0;max-width:none}body{font-size:11pt}}`;
export function renderLeaseHTML(doc) {
  return `<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>${esc(doc.title)}</title><style>${documentStyles}</style></head><body>${renderLeaseBody(doc)}</body></html>`;
}
