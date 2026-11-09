const CATEGORIES=new Set(["source_review","deadline_cutoff","document_readiness","funding_evidence","eligibility_evidence","duplicate_route"]);
const PRIORITIES=new Set(["high","medium","low"]);
const CLOSED=new Set(["rejected","withdrawn","archived","offer","blocked","submitted"]);

export function hostedStatus(advisory,todayUtc){
 if(!advisory||advisory.state==="not_configured")return "No hosted AI advisory has been published. Configure the workflow in GitHub Actions to generate proof-gap priorities.";
 if(advisory.state==="stale_or_invalid")return "Last hosted advisory was stale, superseded or invalid. No model suggestions are shown.";
 if(advisory.state!=="current"||advisory.observation_date!==todayUtc)return "Hosted advisory is no longer current. Run the GitHub Actions workflow again.";
 return Array.isArray(advisory.items)&&advisory.items.length===0?"No additional AI triage suggestions in the current validated run.":"Current validated model proposals require independent review.";
}

export function hostedAdvisories(snapshot,todayUtc){
 const advisory=snapshot?.hosted_ai;
 if(!snapshot||!advisory||advisory.state!=="current"||advisory.status!=="unverified_model_proposal"||advisory.observation_date!==todayUtc)return [];
 if(typeof advisory.source_digest!=="string"||!/^[0-9a-f]{64}$/.test(advisory.source_digest)||!Array.isArray(advisory.items)||advisory.items.length>24)return [];
 const records=new Map((snapshot.records||[]).filter(r=>r.record_type==="tracked"&&!CLOSED.has(r.status)).map(r=>[r.id,r]));
 const seen=new Set(),out=[];
 for(const item of advisory.items){
  if(!item||typeof item!=="object"||!records.has(item.id)||!CATEGORIES.has(item.category)||!PRIORITIES.has(item.priority))return [];
  const key=item.id+"|"+item.category;
  if(seen.has(key))return [];
  seen.add(key);
  out.push({id:item.id,category:item.category,priority:item.priority});
 }
 return out;
}
