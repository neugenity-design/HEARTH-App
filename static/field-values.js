const aliases={
  'driveway':'Driveway parking',
  'in-unit':'In-unit laundry',
  'central air':'Central air conditioning',
  'alarm':'Security system',
  'internet':'Internet ready'
};

export function normaliseMultiValues(value){
  const raw=Array.isArray(value)?value:String(value||'').split(/[\n,;]+/);
  const values=raw.map(item=>String(item).trim()).filter(Boolean).map(item=>{
    const withoutLabel=item.includes(':')?item.slice(item.indexOf(':')+1).trim():item;
    return aliases[withoutLabel.toLowerCase()]||withoutLabel;
  });
  return [...new Set(values)];
}
