import test from "node:test";
import assert from "node:assert/strict";
import {verifiedCutoff,cutoffElapsed,cutoffDescription,cutoffRisk,calendarEvents,exactCutoffReminder} from "../site/modules/deadline-cutoff.mjs";
const r={id:"A1",record_type:"tracked",status:"preparing",name:"Research, Physics; Lab",deadline:"2027-06-01",deadline_time:"23:59",deadline_timezone:"Europe/London",deadline_cutoff_verified:true,deadline_cutoff_utc:"2027-06-01T22:59:00Z"};
test("verified cutoff is an exact UTC instant",()=>{
 assert.equal(verifiedCutoff(r),Date.parse("2027-06-01T22:59:00Z"));
 assert.equal(cutoffElapsed(r,Date.parse("2027-06-01T22:58:00Z")),false);
 assert.equal(cutoffElapsed(r,Date.parse("2027-06-01T22:59:00Z")),true);
 assert.deepEqual(cutoffRisk(r,Date.parse("2027-06-01T22:29:00Z")),{label:"Under 1h",urgency:"red"});
});
test("unverified times never produce verified instants",()=>{
 for(const invalid of [{...r,deadline_cutoff_verified:false},{...r,deadline_cutoff_utc:null},{...r,deadline_cutoff_utc:"2027-06-01T55:59:00Z"}]){
  assert.equal(verifiedCutoff(invalid),null);
  assert.equal(cutoffElapsed(invalid,Date.parse("2028-01-01T00:00:00Z")),false);
 }
 assert.match(cutoffDescription({...r,deadline_cutoff_verified:false}),/unverified/);
});
test("calendar uses UTC for verified cutoff and whole-day reminders otherwise",()=>{
 const out=calendarEvents([r,{...r,id:"A2",deadline_cutoff_verified:false},{...r,id:"A3",status:"submitted",followup:"2027-06-05"}],"MyRepo/PhD");
 assert.match(out,/DTSTART:20270601T225900Z/);
 assert.match(out,/DTEND:20270601T230000Z/);
 assert.match(out,/DTSTART;VALUE=DATE:20270601/);
 assert.match(out,/UID:deadline-A1@MyRepo-PhD/);
 assert.match(out,/UID:followup-A3@MyRepo-PhD/);
 assert.doesNotMatch(out,/UID:deadline-A3/);
 assert.match(out,/Research\\, Physics\\; Lab/);
});

test("verified UTC instants must round-trip through the recorded IANA zone and local clock",()=>{
 assert.equal(verifiedCutoff({...r,deadline_cutoff_utc:"2027-06-01T23:59:00Z"}),null);
 assert.equal(verifiedCutoff({...r,deadline_timezone:"Asia/Tokyo"}),null);
 assert.equal(verifiedCutoff({...r,deadline_cutoff_utc:"2027-02-30T22:59:00Z"}),null);
 assert.equal(verifiedCutoff({...r,deadline_timezone:"Invalid/Zone"}),null);
});

test("exact cutoff reminders are deduplicable, deadline-bound and never sent for submitted or blocked routes",()=>{
 const when=Date.parse("2027-06-01T17:59:00Z");
 const notification=exactCutoffReminder(r,when);
 assert.equal(notification.stage,"6h");
 assert.equal(notification.key,"A1|2027-06-01T22:59:00Z|6h");
 assert.match(notification.body,/recheck the current portal/);
 assert.equal(exactCutoffReminder({...r,status:"submitted"},when),null);
 assert.equal(exactCutoffReminder({...r,status:"blocked"},when),null);
 assert.equal(exactCutoffReminder({...r,deadline_cutoff_verified:false},when),null);
 assert.equal(exactCutoffReminder(r,Date.parse("2027-06-01T23:00:00Z")),null);
 assert.equal(exactCutoffReminder(r,Date.parse("2027-05-01T00:00:00Z")),null);
});
