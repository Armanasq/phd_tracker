import {isDay} from "./domain.mjs";

const STATUSES=new Set(["unconfirmed","shortlisted","preparing","submitted","interview","offer","rejected","withdrawn","blocked","archived"]);
const VERIFICATIONS=new Set(["unverified","needs_review","source_verified","owner_verified"]);
const CONTACT_STATES=new Set(["unrecorded","to_contact","contacted","awaiting_reply","followup_due","replied","declined","completed"]);
const DOCUMENT_STATES=new Set(["unknown","ready","in_progress","not_started","not_applicable"]);
const DOCS=new Set(["academic_cv","research_statement","transcripts","recommendations","english_proof","research_portfolio"]);
const ID=/^LOCAL-[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
const EMAIL=/[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}/i;

function safeText(value,max,field,{required=false}={}){
 if(value===null||value===undefined)value="";
 if(typeof value!=="string")throw new TypeError(field+" must be text");
 const item=value.trim();
 if(item.length>max||/[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]/.test(item)||EMAIL.test(item)||(required&&item.length<3))throw new TypeError("Invalid "+field);
 return item;
}

function optionalDay(value,field){
 if(value===""||value===null||value===undefined)return null;
 if(!isDay(value))throw new TypeError("Invalid "+field);
 return value;
}

export function validateEvidenceUrl(value){
 const item=safeText(value,1800,"source URL");
 if(!item)return "";
 let u;
 try{u=new URL(item)}catch{throw new TypeError("Source URL must be HTTPS")}
 if(u.protocol!=="https:"||!u.hostname||u.username||u.password||u.port||["mail.google.com","gmail.com","accounts.google.com"].includes(u.hostname.toLowerCase())){
  throw new TypeError("Source URL must be a public HTTPS evidence link");
 }
 return u.href;
}

export function createLocalRecord(input,id){
 if(!input||typeof input!=="object"||Array.isArray(input))throw new TypeError("Local opportunity must be an object");
 if(typeof id!=="string"||!ID.test(id))throw new TypeError("Invalid local opportunity ID");
 const documents=Array.isArray(input.documents)?[...new Set(input.documents)]:[];
 if(documents.length>DOCS.size||documents.some(d=>!DOCS.has(d)))throw new TypeError("Invalid document identifiers");
 const inputStates=input.document_states??{};
 if(!inputStates||typeof inputStates!=="object"||Array.isArray(inputStates)||Object.entries(inputStates).some(([key,value])=>!DOCS.has(key)||!DOCUMENT_STATES.has(value)))throw new TypeError("Invalid document states");
 const status=input.status??"unconfirmed";
 const verification=input.verification??"unverified";
 const contactStatus=input.contact_status??"unrecorded";
 const priority=input.priority??"normal";
 if(!STATUSES.has(status)||!VERIFICATIONS.has(verification)||!CONTACT_STATES.has(contactStatus)||!["normal","low","high"].includes(priority))throw new TypeError("Invalid local workflow state");
 const source=validateEvidenceUrl(input.source_url??"");
 const receipt=validateEvidenceUrl(input.receipt??"");
 const name=safeText(input.name,350,"opportunity name",{required:true});
 const nextStep=safeText(input.next_step??"",650,"next action");
 const notes=safeText(input.notes??"",750,"local notes");
 const followup=optionalDay(input.followup,"follow-up date");
 const deadline=optionalDay(input.deadline,"deadline");
 const updated=typeof input.updated_at==="string"&&/^\d{4}-\d{2}-\d{2}T/.test(input.updated_at)?input.updated_at:null;
 return {
  id,record_type:"tracked",local_only:true,name,country:safeText(input.country??"",70,"country"),
  institution:safeText(input.institution??"",160,"institution"),deadline,
  deadline_kind:"Recorded date; cutoff unverified",deadline_type:"unverified",verification,
  verification_note:"User-entered locally; not verified by public source pipeline",
  status,status_confirmed:false,submission_receipt:"",
  documents,document_states:Object.fromEntries(documents.map(key=>[key,inputStates[key]??"unknown"])),
  document_requirements_note:"",followup,contact_status:contactStatus,
  faculty:"Not recorded",source_url:source,secondary_url:"",apply_url:"",
  source_date:null,evidence:"",funding:"",eligibility:"",fit:"",topic:"",next_step:nextStep,
  blockers:"",notes,receipt,priority,decision:"",duplicate_submission_advisory:false,
  recheck_required:!["source_verified","owner_verified"].includes(verification),
  updated_at:updated,
 };
}

export function normalizeLocalRecords(value,committedIds=[]){
 if(!Array.isArray(value)||value.length>1000)throw new TypeError("Local records must be a bounded array");
 const seen=new Set(committedIds),result=[];
 for(const item of value){
  const record=createLocalRecord(item,item?.id);
  if(seen.has(record.id))throw new TypeError("Duplicate opportunity identifier: "+record.id);
  seen.add(record.id);result.push(record);
 }
 return result;
}

export function mergeLocalRecords(existing,incoming,committedIds=[]){
 const old=normalizeLocalRecords(existing,committedIds);
 const added=normalizeLocalRecords(incoming,committedIds);
 const map=new Map(old.map(r=>[r.id,r]));
 let imported=0,skipped=0;
 for(const record of added){
  if(map.has(record.id)){skipped++;continue}
  map.set(record.id,record);imported++;
 }
 if(map.size>1000)throw new TypeError("Maximum 1000 local opportunities");
 return {records:[...map.values()],imported,skipped};
}

const SOURCE_TEXT_FIELDS={
 institution:160,country:70,deadline_kind:200,faculty:160,funding:400,eligibility:380,
 fit:260,topic:220,next_step:650,blockers:420,decision:80,evidence:440,
};

function publicSourceRecord(row){
 if(!row||typeof row!=="object"||Array.isArray(row)||row.local_only)throw new TypeError("Invalid published opportunity");
 if(typeof row.id!=="string"||!/^[A-Za-z0-9][A-Za-z0-9_.-]{0,79}$/.test(row.id))throw new TypeError("Invalid published opportunity ID");
 const name=safeText(row.name,350,"published name");
 if(!name)throw new TypeError("Published opportunity is missing its name");
 const type=row.record_type??"tracked";
 if(!["tracked","candidate"].includes(type))throw new TypeError("Invalid published opportunity type");
 const verification=row.verification??"unverified";
 if(!VERIFICATIONS.has(verification))throw new TypeError("Invalid published verification");
 const status=row.status??"unconfirmed";
 if(!STATUSES.has(status))throw new TypeError("Invalid published application status");
 const deadlineType=row.deadline_type??"unverified";
 if(!["unverified","final","rolling","internal","other"].includes(deadlineType))throw new TypeError("Invalid published deadline type");
 const priority=row.priority??"normal";
 if(!["low","normal","high"].includes(priority))throw new TypeError("Invalid published priority");
 const contact=row.contact_status??"unrecorded";
 if(!CONTACT_STATES.has(contact))throw new TypeError("Invalid published contact state");
 const documents=row.documents??[];
 if(!Array.isArray(documents)||documents.length>DOCS.size||documents.some(d=>!DOCS.has(d))||new Set(documents).size!==documents.length)throw new TypeError("Invalid published documents");
 const documentStates=row.document_states??{};
 if(!documentStates||typeof documentStates!=="object"||Array.isArray(documentStates)||Object.entries(documentStates).some(([key,value])=>!DOCS.has(key)||!DOCUMENT_STATES.has(value)))throw new TypeError("Invalid published document states");
 const source=validateEvidenceUrl(row.source_url??"");
 const application=validateEvidenceUrl(row.apply_url??"");
 const scrubUrl=url=>url?(new URL(url).origin+new URL(url).pathname):"";
 const evidence=safeText(row.evidence??"",440,"published evidence");
 const sourceDate=optionalDay(row.source_date,"published source date");
 if(["source_verified","owner_verified"].includes(verification)&&(!source||!sourceDate||!evidence))throw new TypeError("Published verified evidence must have source URL, source date and note");
 const retained={
  id:row.id,record_type:type,name,verification,status,deadline_type:deadlineType,
  deadline:optionalDay(row.deadline,"published deadline"),followup:optionalDay(row.followup,"published followup"),
  source_url:scrubUrl(source),apply_url:scrubUrl(application),source_date:sourceDate,
  priority,contact_status:contact,documents,
  document_states:Object.fromEntries(documents.map(d=>[d,documentStates[d]??"unknown"])),
 };
 for(const [key,max] of Object.entries(SOURCE_TEXT_FIELDS)){
  const value=safeText(row[key]??"",max,"published "+key);
  if(value)retained[key]=value;
 }
 if(row.duplicate_submission_advisory===true)retained.duplicate_submission_advisory=true;
 return retained;
}

export function exportIndependentSource(records,today,timezone="UTC",committed=[]){
 if(!isDay(today))throw new TypeError("Invalid export date");
 if(typeof timezone!=="string"||!/^[-_A-Za-z/]{2,80}$/.test(timezone))throw new TypeError("Invalid timezone");
 if(!Array.isArray(committed)||committed.length>5000)throw new TypeError("Invalid published opportunity list");
 const existing=committed.map(publicSourceRecord);
 const ids=existing.map(record=>record.id);
 if(new Set(ids).size!==ids.length)throw new TypeError("Duplicate published opportunity identifier");
 const local=normalizeLocalRecords(records,ids);
 if(existing.length+local.length>5000)throw new TypeError("Maximum 5000 public opportunity records");
 return {
  schema_version:1,as_of:today,timezone,
  records:[...existing,...local.map(r=>({
   id:r.id,record_type:"tracked",name:r.name,institution:r.institution,country:r.country,deadline:r.deadline,
   verification:"unverified",source_url:r.source_url?new URL(r.source_url).origin+new URL(r.source_url).pathname:"",
   documents:r.documents,
  }))],
 };
}
