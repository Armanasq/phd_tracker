const VERIFIED=new Set(["source_verified","owner_verified"]);
const ISO_DATE=/^\d{4}-\d{2}-\d{2}$/;
const STAGES=Object.freeze(["review","reviewed","closed","staged"]);

export function candidateAssessment(record,today) {
  if (!record || record.record_type!=="candidate" || typeof record.id!=="string") throw new TypeError("Expected a research candidate");
  if (!ISO_DATE.test(today)) throw new TypeError("Expected an ISO observation date");
  const date=typeof record.deadline==="string"&&ISO_DATE.test(record.deadline)?record.deadline:null;
  const rolling=record.deadline_type==="rolling"||record.deadline_kind==="rolling";
  const closed=Boolean(date&&!rolling&&date<today);
  const reviewed=VERIFIED.has(record.verification)&&Boolean(record.source_url);
  const reasons=[];
  if (!reviewed) reasons.push("Official source verification remains incomplete");
  if (!record.source_url) reasons.push("No primary source URL recorded");
  if (!date&&!rolling) reasons.push("Closing date unrecorded");
  if (!record.funding) reasons.push("Funding not established");
  if (!record.eligibility) reasons.push("Eligibility not established");
  if (record.duplicate_submission_advisory) reasons.push("Potential duplicate route requires review");
  if (closed) reasons.unshift("Recorded closing date has passed; current availability is unknown");
  const stage=record.promoted?"staged":closed?"closed":reviewed?"reviewed":"review";
  const action=stage==="reviewed"?"Review and stage promotion":stage==="closed"?"Verify a newer or reopened call":stage==="staged"?"Confirm staged changes in Updates":"Verify the primary institution source";
  return {record,stage,action,reasons,deadline:date,reviewed,closed};
}

export function candidateQueue(records,today,{stage="all",query=""}={}) {
  if (!Array.isArray(records)) throw new TypeError("Expected opportunity records");
  if (stage!=="all"&&!STAGES.includes(stage)) throw new TypeError("Unknown candidate filter");
  const q=String(query).trim().toLocaleLowerCase().slice(0,200);
  const rows=records.filter(x=>x?.record_type==="candidate").map(x=>candidateAssessment(x,today));
  const counts={total:rows.length,review:0,reviewed:0,closed:0,staged:0};
  for(const item of rows)counts[item.stage]++;
  const filtered=rows.filter(x=>(stage==="all"||x.stage===stage)&&
    (!q||[x.record.name,x.record.institution,x.record.country,x.record.topic,x.record.id].some(v=>String(v||"").toLocaleLowerCase().includes(q))));
  const order={reviewed:0,review:1,staged:2,closed:3};
  filtered.sort((a,b)=>order[a.stage]-order[b.stage]||
    (a.deadline||"9999-12-31").localeCompare(b.deadline||"9999-12-31")||
    String(a.record.name||a.record.id).localeCompare(String(b.record.name||b.record.id)));
  return {items:filtered,counts,stage,query:q};
}
