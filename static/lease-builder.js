import {californiaTemplate} from './lease-templates.js';
import {escapeHTML as esc,dropdown} from './controls.js';
import {createLeaseDocument,leaseContext,newSection,sectionTypes,moveSection,fillTokens,documentIssues,renderLeaseHTML} from './lease-document.js';

export function mountLeaseBuilder(root,{lease,state,save,attach,filesHTML,onSaved}) {
  let record=lease,doc=structuredClone(lease.document||createLeaseDocument(lease,state));
  let dirty=!lease.document,mode='edit',busy=false,removed=null;
  const back=`#leases/${lease.id}`;
  const initialHash=location.hash;
  const button=(title,action,attrs='')=>`<button type="button" data-lease-action="${action}" ${attrs}>${esc(title)}</button>`;
  const resolved=value=>fillTokens(value,doc.context);
  const field=(label,value,attrs='',multiline=false)=>`<label class="field">${esc(label)}${multiline?`<textarea ${attrs} rows="5">${esc(resolved(value))}</textarea>`:`<input ${attrs} value="${esc(resolved(value))}">`}</label>`;
  const status=text=>{root.querySelector('#lease-save-status').textContent=text;};
  const message=(text,error=true)=>{const element=root.querySelector('#lease-message');element.textContent=text;element.className=error?'form-error':'note';};
  function setDirty(){dirty=true;status('Unsaved changes');}

  function sectionEditor(section,index){
    return `<section class="panel lease-section" data-section="${esc(section.id)}"><div class="panel-head"><div><h2>${index+1}. ${esc(section.title||'Untitled section')}</h2><p>${esc(sectionTypes.find(t=>t[0]===section.type)?.[1]||section.type)}</p></div><div class="actions">${button('↑','up',`aria-label="Move section ${index+1} up" ${index===0?'disabled':''}`)}${button('↓','down',`aria-label="Move section ${index+1} down" ${index===doc.sections.length-1?'disabled':''}`)}${button('Remove','remove',`aria-label="Remove section ${index+1}"`)}</div></div><div class="panel-body"><label class="field check"><input type="checkbox" data-section-field="enabled" ${section.enabled!==false?'checked':''}>Include in document</label><div class="form-grid">${field('Section title',section.title,'data-section-field="title"')}${['text','signature'].includes(section.type)?`<div class="field full">${field(section.type==='signature'?'Signature introduction':'Section text',section.body,'data-section-field="body"',true)}</div>`:''}</div>${['details','charges'].includes(section.type)?`<div class="lease-row-editors">${section.rows.map((row,rowIndex)=>`<div class="lease-row-editor" data-row="${rowIndex}">${field('Label',row.label,'data-row-field="label"')}${field('Value',row.value,'data-row-field="value"')}${button('Remove row','remove-row',`aria-label="Remove row ${rowIndex+1} from section ${index+1}"`)}</div>`).join('')}${button('+ Add row','add-row')}</div>`:''}${section.type==='signature'?'<p class="muted small">Blank signature and date lines will be included for the owner and each tenant. Names come from Document details below.</p>':''}</div></section>`;
  }

  function draw(){
    root.innerHTML=`<div class="lease-builder"><div class="page-head"><div><p class="eyebrow">${esc(lease.name)}</p><h1>Lease document</h1><p>Build and review your lease section by section.</p></div><div class="actions">${button('Back to lease','back')}${button('Save draft','save','class="primary"')}${button(mode==='edit'?'Preview':'Edit sections','toggle')}${button('Print / Save PDF','print')}${button('Generate document','generate')}</div></div><div class="lease-builder-status"><span class="badge">Draft / unsigned</span><span id="lease-save-status" role="status">${dirty?'Unsaved changes':'Saved · revision '+doc.revision}</span></div><p id="lease-message" class="form-error" role="alert"></p><p class="muted small">${esc(doc.templateId===californiaTemplate.id?californiaTemplate.name:(doc.templateName||'Custom lease document'))}${doc.templateId===californiaTemplate.id?' · '+esc(californiaTemplate.description):''}</p><p class="note">This draft starts with the details recorded on your lease. Add your lease clauses and review the document before signing. Document edits do not change the rent or payment records.</p>${mode==='preview'?'<iframe class="lease-preview" title="Lease document preview"></iframe>':`<section class="panel"><div class="panel-body"><div class="actions"><label class="field">Template${dropdown({attrs:{id:'lease-template','aria-label':'Lease template'},options:[[californiaTemplate.id,californiaTemplate.name],['basic','Basic lease outline']],value:doc.templateId||'basic'})}</label>${button('Use template','template')}</div><div class="form-grid">${field('Document title',doc.title,'data-document-field="title"')}${field('Subtitle',doc.subtitle,'data-document-field="subtitle"')}<div class="field full">${field('Introduction',doc.introduction||'','data-document-field="introduction"',true)}</div></div></div></section><div class="lease-sections">${doc.sections.map(sectionEditor).join('')}</div><div class="panel"><div class="panel-body actions"><label class="field">Section type${dropdown({attrs:{id:'lease-section-type','aria-label':'New section type'},options:sectionTypes})}</label>${button('+ Add section','add')}${removed?button('Undo remove','undo'):''}</div></div><details class="panel lease-context"><summary>Document details · names, property & rental terms</summary><div class="panel-body"><p class="muted small">These values fill unchanged sections. Changes typed directly into a section take precedence.</p><div class="form-grid">${Object.entries(doc.context).map(([key,value])=>field(key.replace(/_/g,' '),value,`data-context-field="${esc(key)}"`)).join('')}</div><p>${button('Refresh unchanged values from lease','refresh')}</p></div></details>`}<details class="panel lease-context"><summary>Attached lease documents</summary><div class="panel-body">${filesHTML()||'<p>No documents attached yet. Attach a signed lease from the lease record.</p>'}</div></details></div>`;
    if(mode==='preview')root.querySelector('.lease-preview').srcdoc=renderLeaseHTML(doc);
  }

  async function saveDraft(){
    if(!dirty&&record.document)return;
    const next={...doc,revision:(Number(record.document?.revision)||0)+1,savedAt:new Date().toISOString()};
    record=await save(record,next);doc=structuredClone(record.document);dirty=false;
    status('Saved · revision '+doc.revision);onSaved?.();
  }
  const handleInput=event=>{
    const input=event.target;
    if(input.dataset.documentField)doc[input.dataset.documentField]=input.value;
    else if(input.dataset.contextField)doc.context[input.dataset.contextField]=input.value;
    else {
      const section=doc.sections.find(s=>s.id===input.closest('[data-section]')?.dataset.section);
      if(!section)return;
      if(input.dataset.sectionField)section[input.dataset.sectionField]=input.type==='checkbox'?input.checked:input.value;
      else if(input.dataset.rowField)section.rows[Number(input.closest('[data-row]').dataset.row)][input.dataset.rowField]=input.value;
      else return;
    }
    setDirty();
  };
  const handleClick=async event=>{
    const control=event.target.closest('[data-lease-action]');if(!control||busy)return;
    const action=control.dataset.leaseAction,id=control.closest('[data-section]')?.dataset.section;
    const section=doc.sections.find(s=>s.id===id);
    message('');
    try{
      if(action==='back'){if(!dirty||window.confirm('Discard unsaved lease document changes?')){dirty=false;location.hash=back;}return;}
      if(action==='toggle'){mode=mode==='edit'?'preview':'edit';draw();return;}
      if(action==='save'||action==='generate'){
        if(action==='generate'){const issues=documentIssues(doc);if(issues.length){message(issues.join(' '));return;}}
        busy=true;root.inert=true;root.querySelectorAll('.page-head button').forEach(b=>b.disabled=true);
        await saveDraft();
        if(action==='generate'){
          const filename=`${lease.name.replace(/[^\w -]/g,'').slice(0,70)||'Lease'} - revision ${doc.revision}.html`;
          const file=new File([renderLeaseHTML(doc)],filename,{type:'text/html'});
          await attach(file,lease.id);
          const url=URL.createObjectURL(file),link=document.createElement('a');link.href=url;link.download=filename;link.click();setTimeout(()=>URL.revokeObjectURL(url),1000);
          mode='preview';draw();message('Document generated and attached to this lease. Use Print / Save PDF for a PDF copy.',false);
        }else{draw();status('Saved · revision '+doc.revision);}
        return;
      }
      if(action==='print'){
        mode='preview';draw();const frame=root.querySelector('.lease-preview');
        frame.onload=()=>{frame.contentWindow.focus();frame.contentWindow.print();};
        frame.srcdoc=renderLeaseHTML(doc);return;
      }
      if(action==='template'){if(!window.confirm('Replace this draft with the selected template? Saved documents and attached files are kept.'))return;doc=createLeaseDocument(record,state,root.querySelector('#lease-template').value);removed=null;}else if(action==='add'){
        const type=root.querySelector('#lease-section-type').value;
        if(type==='signature'&&doc.sections.some(s=>s.type==='signature')){message('A signature section is already included. Edit the existing section.');return;}
        const created=newSection(type),signature=doc.sections.findIndex(s=>s.type==='signature');
        doc.sections.splice(signature<0?doc.sections.length:signature,0,created);
      }else if(action==='remove'){removed={section,index:doc.sections.indexOf(section)};doc.sections=doc.sections.filter(s=>s.id!==id);}
      else if(action==='undo'&&removed){doc.sections.splice(removed.index,0,removed.section);removed=null;}
      else if(action==='up'||action==='down')doc.sections=moveSection(doc.sections,id,action==='up'?-1:1);
      else if(action==='add-row')section.rows.push({label:'',value:''});
      else if(action==='remove-row')section.rows.splice(Number(control.closest('[data-row]').dataset.row),1);
      else if(action==='refresh')doc.context=leaseContext(record,state);
      else return;
      dirty=true;draw();
    }catch(error){message(error.message);}
    finally{busy=false;root.inert=false;root.querySelectorAll('.page-head button').forEach(b=>b.disabled=false);}
  };
  const beforeUnload=event=>{if(dirty){event.preventDefault();event.returnValue='';}};
  const guardLink=event=>{const link=event.target.closest('a[href^="#"]');if(link&&dirty){if(!window.confirm('Discard unsaved lease document changes?')){event.preventDefault();event.stopImmediatePropagation();}else dirty=false;}};
  root.addEventListener('input',handleInput);root.addEventListener('click',handleClick);
  document.addEventListener('click',guardLink,true);window.addEventListener('beforeunload',beforeUnload);
  draw();
  const dispose=()=>{root.removeEventListener('input',handleInput);root.removeEventListener('click',handleClick);document.removeEventListener('click',guardLink,true);window.removeEventListener('beforeunload',beforeUnload);};
  dispose.canLeave=()=>!dirty||window.confirm('Discard unsaved lease document changes?');
  dispose.route=initialHash;
  return dispose;
}
