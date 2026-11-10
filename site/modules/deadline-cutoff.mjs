const INSTANT=/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:00Z$/;
const DAY=/^\d{4}-\d{2}-\d{2}$/;
const NAME=/^[A-Za-z0-9][A-Za-z0-9_.-]{0,79}$/;

export function verifiedCutoff(record){
 if(record?.deadline_cutoff_verified!==true||typeof record.deadline_cutoff_utc!=="string"||!INSTANT.test(record.deadline_cutoff_utc))return null;
 const utc=Date.parse(record.deadline_cutoff_utc);
 if(!Number.isFinite(utc)||!DAY.test(record.deadline||"")||typeof record.deadline_time!=="string"||typeof record.deadline_timezone!=="string")return null;
 return utc;
}

export function cutoffElapsed(record,now=Date.now()){
 const utc=verifiedCutoff(record);
 return utc!==null&&Number.isFinite(now)&&now>=utc;
}

export function cutoffDescription(record){
 const time=record?.deadline_time,zone=record?.deadline_timezone;
 if(verifiedCutoff(record)!==null)return "Source-attested cutoff: "+time+" ("+zone+"); recheck current portal";
 if(typeof time==="string"&&time&&typeof zone==="string"&&zone)return "Recorded "+time+" ("+zone+"), unverified; confirm current portal";
 return "Official closing hour and timezone not verified";
}

export function cutoffRisk(record,now=Date.now()){
 const utc=verifiedCutoff(record);
 if(utc===null)return null;
 const left=utc-now;
 if(left<=0)return {label:"Cutoff elapsed",urgency:"red"};
 if(left<=3600000)return {label:"Under 1h",urgency:"red"};
 if(left<=86400000)return {label:Math.ceil(left/3600000)+"h left",urgency:"red"};
 if(left<=259200000)return {label:Math.ceil(left/86400000)+"d left",urgency:"warning"};
 return null;
}

function icsText(value){return String(value??"").replace(/\\/g,"\\\\").replace(/\r\n|\r|\n/g,"\\n").replace(/;/g,"\\;").replace(/,/g,"\\,")}
function icsStamp(ms){return new Date(ms).toISOString().replace(/[-:]/g,"").replace(/\.\d{3}Z$/,"Z")}
function icsDay(date){return date.replace(/-/g,"")}

export function calendarEvents(records,scope="phd-atlas"){
 const namespace=String(scope).replace(/[^A-Za-z0-9._-]/g,"-").slice(0,140)||"phd-atlas";
 const result=["BEGIN:VCALENDAR","VERSION:2.0","CALSCALE:GREGORIAN","PRODID:-//PhD Atlas//Application Tracker//EN"];
 for(const r of records||[]){
  if(r?.record_type!=="tracked"||!NAME.test(r.id||"")||["archived","withdrawn","rejected","offer","blocked"].includes(r.status))continue;
  const verified=verifiedCutoff(r);
  if(r.status!=="submitted"&&DAY.test(r.deadline||"")){
   const start=verified===null?"DTSTART;VALUE=DATE:"+icsDay(r.deadline):"DTSTART:"+icsStamp(verified);
   const end=verified===null?"DTEND;VALUE=DATE:"+icsDay(new Date(Date.parse(r.deadline+"T12:00:00Z")+86400000).toISOString().slice(0,10)):"DTEND:"+icsStamp(verified+60000);
   result.push("BEGIN:VEVENT","UID:deadline-"+r.id+"@"+namespace,start,end,
    "SUMMARY:"+icsText(r.name)+(verified===null?" (verify cutoff)":" (source-attested cutoff)"),
    "DESCRIPTION:"+icsText(cutoffDescription(r)),"END:VEVENT");
  }
  if(r.status==="submitted"&&DAY.test(r.followup||"")){
   const end=new Date(Date.parse(r.followup+"T12:00:00Z")+86400000).toISOString().slice(0,10);
   result.push("BEGIN:VEVENT","UID:followup-"+r.id+"@"+namespace,"DTSTART;VALUE=DATE:"+icsDay(r.followup),
    "DTEND;VALUE=DATE:"+icsDay(end),"SUMMARY:"+icsText(r.name)+" (post-submission follow-up)",
    "DESCRIPTION:Owner-recorded follow-up. Check the private portal record.","END:VEVENT");
  }
 }
 return result.concat("END:VCALENDAR","").join("\r\n");
}
