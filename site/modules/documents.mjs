const STATES=new Set(["ready","in_progress","not_started","not_applicable","unknown"]);
const ACTIVE=new Set(["unconfirmed","shortlisted","preparing","blocked","interview","offer"]);

export function portfolioDocumentInventory(records) {
  if (!Array.isArray(records)) throw new TypeError("Expected an array of application records");
  const groups=new Map();
  const summary={tracked:0,active:0,unconfirmed_requirements:0,listed_requirements:0,unknown:0,ready:0,in_progress:0,not_started:0,not_applicable:0};
  for(const record of records) {
    if(!record||record.record_type!=="tracked")continue;
    summary.tracked++;
    const active=ACTIVE.has(record.status);
    if(active)summary.active++;
    const keys=Array.isArray(record.documents)?[...new Set(record.documents.filter(k=>typeof k==="string"&&/^[a-z][a-z0-9_]{0,63}$/.test(k)))]:[];
    if(!keys.length){if(active)summary.unconfirmed_requirements++;continue;}
    for(const key of keys) {
      const raw=record.document_states?.[key];
      const state=STATES.has(raw)?raw:"unknown";
      const item=groups.get(key)||{id:key,applications:[],states:{ready:0,in_progress:0,not_started:0,unknown:0,not_applicable:0},active:0};
      item.applications.push({
        id:String(record.id||""),
        name:String(record.name||record.id||""),
        status:record.status||"unconfirmed",
        state,
        active,
        verified_requirements:Boolean(["source_verified","owner_verified"].includes(record.verification)&&String(record.document_requirements_note||"").trim()),
        deadline:record.deadline||null
      });
      item.states[state]++;
      if(active){item.active++;summary.listed_requirements++;summary[state]++;}
      groups.set(key,item);
    }
  }
  const items=[...groups.values()].map(item=>({
    ...item,
    unknown_or_unstarted:item.applications.filter(x=>x.active&&["unknown","not_started"].includes(x.state)).length,
    reported_ready:item.applications.filter(x=>x.active&&x.state==="ready").length,
    verified_requirements:item.applications.filter(x=>x.active&&x.verified_requirements).length
  }));
  items.sort((a,b)=>b.unknown_or_unstarted-a.unknown_or_unstarted||b.active-a.active||a.id.localeCompare(b.id));
  return {items,summary};
}
