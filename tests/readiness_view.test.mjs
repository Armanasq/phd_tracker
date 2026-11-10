import test from "node:test";
import assert from "node:assert/strict";
import {renderReadinessView} from "../site/modules/readiness-view.mjs";
const row={id:"A",record:{id:"A",name:"Research <script>bad</script>",next_step:"Verify <source>"},phase:"active",due:2,followup:null,openProof:2,knownPreparation:0,top:{label:"Check <portal>",detail:"Unknown does not mean missing"},tasks:[]};
const report={active:[row],submitted:[],halted:[],reusable:[{key:"academic_cv",name:"Academic CV",required:2,unknown:1,not_started:1,in_progress:0}],collisions:[],totals:{active:1,close14:1,deadlineProof:1,knownDocumentGaps:0,submittedWithoutReceipt:0}};
const esc=x=>String(x??"").replace(/[&<>"]/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c]));
const render=filter=>renderReadinessView({report,filter,heading:(a,b,c)=>a+b+c,kpi:(a,b)=>a+b,rowButton:r=>'<button>'+esc(r.name)+'</button>',button:(label,action,value)=>'<button data-action="'+action+'" data-value="'+(value||"")+'">'+label+'</button>',pill:x=>'<span>'+x+'</span>',dateRisk:x=>'<span>'+x+'</span>',stamp:x=>x,escape:esc});
test("readiness dashboard shows grounded actions and escapes user text",()=>{
 const html=render("all");
 assert.match(html,/Next defensible actions/);
 assert.match(html,/data-action="record" data-value="A"/);
 assert.match(html,/Research &lt;script&gt;/);
 assert.match(html,/Verify &lt;source&gt;/);
 assert.match(html,/Check &lt;portal&gt;/);
 assert.doesNotMatch(html,/<script>/);
 assert.match(html,/Shared document demand/);
 assert.match(html,/Post-submission verification/);
});
test("filters never invent document work",()=>{
 assert.match(render("proof"),/Check &lt;portal&gt;/);
 assert.match(render("prep"),/No active applications match this filter/);
 assert.match(render("document:academic_cv"),/No active applications match this filter/);
 assert.match(render("document:forged"),/No active applications match this filter/);
});
