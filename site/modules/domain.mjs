const STATUSES = new Set(["unconfirmed","shortlisted","preparing","submitted","interview","offer","rejected","withdrawn","blocked","archived"]);
const VERIFICATIONS = new Set(["unverified","needs_review","source_verified","owner_verified"]);
const DOC_STATES = new Set(["unknown","ready","in_progress","not_started","not_applicable"]);
const CLOSED = new Set(["rejected","withdrawn","archived","offer"]);
const DAY_MS = 86_400_000;
const dayPattern = /^\d{4}-\d{2}-\d{2}$/;

export function isDay(value) {
  if(typeof value!=="string" || !dayPattern.test(value)) return false;
  const date=new Date(value+"T12:00:00.000Z");
  return !Number.isNaN(date.valueOf()) && date.toISOString().slice(0,10)===value;
}

export function daysUntil(date, today) {
  if(!isDay(date) || !isDay(today)) return null;
  return Math.round((Date.parse(date+"T12:00:00.000Z")-Date.parse(today+"T12:00:00.000Z"))/DAY_MS);
}

export function isClosed(record){return CLOSED.has(record?.status)}

export function isActionable(record,today) {
  if(!record || record.record_type!=="tracked" || isClosed(record) || record.status==="blocked")return false;
  if(record.status==="submitted"){
    const follow=daysUntil(record.followup,today);
    return follow!==null&&follow<=14;
  }
  const due=daysUntil(record.deadline,today);
  return due===null||due>=0;
}

export function documentReadiness(record) {
  const stated=Array.isArray(record?.documents)?record.documents:[];
  const states=record?.document_states??{};
  if(!stated.length) return {state:"unknown",label:"Requirements unconfirmed",verified:false};
  const values=stated.map(key=>DOC_STATES.has(states[key])?states[key]:"unknown");
  if(values.includes("not_started")) return {state:"incomplete",label:"Document gap recorded",verified:false};
  if(values.includes("unknown"))return {state:"unknown",label:"Readiness not verified",verified:false};
  if(values.includes("in_progress"))return {state:"in_progress",label:"Documents in progress",verified:false};
  const evidence=record.verification==="owner_verified"||record.verification==="source_verified";
  const sourceScope=Boolean(record.document_requirements_note?.trim());
  return evidence&&sourceScope
    ?{state:"ready",label:"Listed documents ready; check portal",verified:true}
    :{state:"provisional",label:"Documents marked ready; requirements unverified",verified:false};
}

export function riskSignal(record,today) {
  const due=daysUntil(record?.deadline,today);
  if(record?.status==="blocked")return"Blocked";
  if(record?.status==="submitted"){
    const follow=daysUntil(record.followup,today);
    return follow===null?"Submitted":follow<=0?"Follow-up overdue":follow<=14?"Follow-up due":"Submitted";
  }
  if(isClosed(record))return"Closed";
  if(due!==null&&due<0)return"Expired";
  if(documentReadiness(record).state==="incomplete")return"Confirmed gap";
  if(record?.duplicate_submission_advisory)return"Duplicate route caution";
  if(due!==null&&due<=7)return"Urgent";
  if(!VERIFICATIONS.has(record?.verification)||!["source_verified","owner_verified"].includes(record.verification))return"Verify";
  return"Review";
}

export function priorityScore(record,today) {
  const due=daysUntil(record?.deadline,today);
  if(!isActionable(record,today))return -100;
  if(record.status==="submitted"){
    const follow=daysUntil(record.followup,today);
    return (follow<=0?102:follow<=3?74:follow<=7?46:24)+(record.priority==="high"?20:0);
  }
  let p=due===null?5:due===0?100:due<=3?80:due<=7?56:due<=14?35:due<=30?18:3;
  if(!["source_verified","owner_verified"].includes(record.verification))p+=16;
  if(record.duplicate_submission_advisory)p+=18;
  if(documentReadiness(record).state==="incomplete")p+=16;
  const follow=daysUntil(record.followup,today);
  if(follow!==null&&follow<=2)p+=28;
  if(record.status==="preparing")p+=6;
  if(record.priority==="high")p+=20;
  if(record.priority==="low")p-=12;
  return p;
}

export function validateSnapshot(snapshot) {
  if(!snapshot||typeof snapshot!=="object"||snapshot.schema_version!==1||!Array.isArray(snapshot.records)||!Array.isArray(snapshot.providers)){
    return {ok:false,error:"The source data is incompatible with this version. Reload or inspect the repository evidence."};
  }
  const ids=new Set();
  for(const [i,r] of snapshot.records.entries()){
    if(!r||typeof r!=="object"||typeof r.id!=="string"||!r.id.trim()||ids.has(r.id)){
      return {ok:false,error:"The source contains duplicate or invalid application identifiers (row "+(i+1)+")."};
    }
    ids.add(r.id);
    if(typeof r.name!=="string"||!STATUSES.has(r.status)||!VERIFICATIONS.has(r.verification)||!["tracked","candidate"].includes(r.record_type)||(r.deadline!==null&&!isDay(r.deadline))){
      return {ok:false,error:"An application record is malformed (source ID "+r.id+")."};
    }
  }
  return {ok:true,ids};
}

export function draftState(draft,source){
  if(!draft)return"none";
  if(!source)return"missing-source";
  const current=source.updated_at||"";
  if(typeof draft.base_updated_at!=="string")return"needs-review";
  const expected=draft.base_updated_at;
  const comparable=["status","verification","followup","contact_status","next_step","priority"];
  const equal=comparable.every(k=>draft[k]===undefined||draft[k]===source[k])
    &&Object.entries(draft.documents||{}).every(([key,value])=>source.document_states?.[key]===value);
  if(equal&&current!==expected&&draft._sync_status==="pending")return"committed";
  if(current!==expected)return"conflict";
  return draft._sync_status==="pending"?"pending":"draft";
}

export function applyRecordFilters(items,filters,today) {
  const q=String(filters.query||"").trim().toLocaleLowerCase();
  return items.filter(r=>{
    if(filters.scope==="tracked"&&r.record_type!=="tracked")return false;
    if(filters.scope==="candidate"&&r.record_type!=="candidate")return false;
    if(q && ![r.id,r.name,r.country,r.institution,r.topic,r.faculty,r.next_step,r.funding,r.eligibility,r.evidence].join(" ").toLocaleLowerCase().includes(q))return false;
    if(filters.status&&filters.status!=="all"&&r.status!==filters.status)return false;
    if(filters.verification&&filters.verification!=="all"&&r.verification!==filters.verification)return false;
    if(filters.country&&filters.country!=="all"&&r.country!==filters.country)return false;
    const d=daysUntil(r.deadline,today),h=String(filters.horizon||"all");
    if(h==="expired")return d!==null&&d<0;
    if(h==="unknown")return d===null;
    if(h!=="all")return d!==null&&d>=0&&d<=Number(h);
    return true;
  });
}

export function deadlineCollisions(items,today,limit=30) {
  const groups=new Map();
  for(const r of items){
    if(!isActionable(r,today)||r.status==="submitted"||!isDay(r.deadline))continue;
    const current=groups.get(r.deadline)||[];
    current.push(r.id);
    groups.set(r.deadline,current);
  }
  return Array.from(groups,([date,ids])=>({date,ids,count:ids.length}))
    .filter(x=>x.count>1).sort((a,b)=>a.date.localeCompare(b.date)).slice(0,limit);
}

export function freshnessState(asOf,today) {
  const delta=daysUntil(asOf,today);
  const days=delta===null?null:-delta;
  if(days===null)return{state:"unknown",days:null,label:"Source timestamp unavailable"};
  if(days<0)return{state:"future",days:Math.abs(days),label:"Source timestamp is ahead of the local date"};
  if(days>=14)return{state:"stale",days,label:"Evidence snapshot is "+days+" days old"};
  if(days>=3)return{state:"aging",days,label:"Evidence snapshot is "+days+" days old"};
  return{state:"current",days,label:days===0?"Updated today":"Evidence refreshed "+days+" days ago"};
}
