import test from "node:test";
import assert from "node:assert/strict";
import {createOperations} from "../site/modules/operations.mjs";

function deferred(){
 let resolve,reject;
 const promise=new Promise((ok,fail)=>{resolve=ok;reject=fail;});
 return {promise,resolve,reject};
}

function harness(request){
 const original=globalThis.document;
 globalThis.document={addEventListener(){}};
 try{
  return createOperations({request,onChange(){},onReload:async()=>{},
   getRecords:()=>[],notify(){}});
 }finally{globalThis.document=original;}
}

test("pending private requests cannot repopulate operations after disconnect",async()=>{
 const first=deferred(),second=deferred();
 let calls=0;
 const operations=harness(()=>++calls===1?first.promise:second.promise);
 assert.match(operations.view(),/Loading verified/);
 operations.reset();
 first.resolve({profile:{},proof_queue:{items:[]},referees:[]});
 await new Promise(resolve=>setImmediate(resolve));
 assert.match(operations.view(),/Loading verified/);
 assert.equal(calls,2);
 second.resolve({profile:{},proof_queue:{items:[]},referees:[]});
 await new Promise(resolve=>setImmediate(resolve));
 assert.match(operations.view(),/Application operations/);
 assert.doesNotMatch(operations.view(),/Retry private data/);
});

test("private fetch failure exposes a retry instead of an empty success",async()=>{
 const operations=harness(async()=>{throw new Error("Private SQLite request failed");});
 operations.view();
 await new Promise(resolve=>setImmediate(resolve));
 const html=operations.view();
 assert.match(html,/role="alert"/);
 assert.match(html,/Private SQLite request failed/);
 assert.match(html,/Retry private data/);
 await assert.rejects(operations.reload(),/Private SQLite request failed/);
});

test("invalid private response is rejected instead of creating a portfolio",async()=>{
 const operations=harness(async()=>[]);
 operations.view();
 await new Promise(resolve=>setImmediate(resolve));
 assert.match(operations.view(),/invalid response/);
});
