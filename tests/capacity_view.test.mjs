import test from "node:test";
import assert from "node:assert/strict";
import {renderCapacityReport, capacityCsv} from "../site/modules/capacity-view.mjs";

const esc = x => String(x ?? "").replace(/[&<>"']/g, c => ({"&":"&amp;","<":"&lt;", ">":"&gt;", '"':"&quot;", "'":"&#39;"}[c]));
const report = {status:"over_capacity",baseline:{total_work_hours:8,total_hours_unallocated:2},with_shared_documents:{total_work_hours:12,total_hours_unallocated:6},unallocated:[{task_type:"application",task_id:"application:A",application_id:"A",hours_unallocated:2,deadline:"2027-01-01"}],unallocated_shared_documents:[{task_type:"document",task_id:"document:academic_cv",hours_unallocated:4,deadline:"2027-01-01"}],deadline_bottlenecks:[{deadline:"2027-01-01",due_work_hours:12,available_hours:6,minimum_shortfall_hours:6}],unknown_effort_or_date:[{application_id:"A",reason:"Effort unestimated"}],unknown_document_effort:[],unconfirmed_document_requirements:[],shared_document_hours:{academic_cv:4},assumptions:["No fabricated capacity"],scheduled:[{date:"2027-01-01",task_type:"application",task_id:"application:A",application_id:"=SUM(1)",hours:1}],scheduled_shared_documents:[{date:"2027-01-01",task_type:"document",task_id:"document:academic_cv",hours:1}]};

test("capacity view contrasts baseline and shared effort and discloses assumptions",()=>{
 const html=renderCapacityReport({report,esc,byId:id=>id==="A"?{name:"Synthetic programme"}:null,button:()=>"<button>Export</button>"});
 for(const term of ["Application effort","Shared preparation","Base shortfall","Combined shortfall","Deadline bottlenecks","Unallocated work","No fabricated capacity"])assert.ok(html.includes(term),term);
 assert.ok(!html.includes("undefined"));
});
test("allocation CSV includes document work and neutralizes formulas",()=>{
 const result=capacityCsv(report);
 assert.match(result,/"date","task_type","task_id","application_id","hours"/);
 assert.match(result,/"'=SUM\(1\)"/);
 assert.match(result,/document:academic_cv/);
 assert.equal(result.split("\r\n").length,3);
 assert.throws(()=>capacityCsv({}),TypeError);
});
