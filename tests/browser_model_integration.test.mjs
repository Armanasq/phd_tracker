import test from "node:test";
import assert from "node:assert/strict";
import {createBrowserModel} from "../site/modules/browser-model.mjs";

test("static Pages mode discovers and invokes a local model without credentials", async () => {
  const old = {location:globalThis.location,localStorage:globalThis.localStorage,
    document:globalThis.document,fetch:globalThis.fetch};
  const stored = new Map(), calls = [], notices = [];
  try {
    globalThis.location = {origin:"https://example.github.io",pathname:"/phd_tracker/"};
    globalThis.localStorage = {
      getItem:key=>stored.get(key)??null,
      setItem:(key,value)=>stored.set(key,value)
    };
    globalThis.document = {getElementById:()=>null};
    globalThis.fetch = async(url,options={}) => {
      calls.push({url,options});
      if (url.endsWith("/models")) return Response.json({data:[{id:"synthetic-chat"}]});
      if (url.endsWith("/chat/completions")) return Response.json({
        model:"synthetic-chat",
        choices:[{message:{role:"assistant",content:"Synthetic local reply"}}],
        usage:{prompt_tokens:9,completion_tokens:5}
      });
      return Response.json({error:"Unknown endpoint"},{status:404});
    };
    const browser = createBrowserModel({notify:x=>notices.push(x),onChange:()=>{},
      navigate:()=>{},getSourceRecords:()=>[{id:"public-1",name:"Public opportunity"}]});
    assert.match(browser.render("settings"),/Local model connection/);
    await browser.submit({target:{dataset:{osForm:"bm-config"},elements:{
      baseUrl:{value:"http://127.0.0.1:11434/v1"},model:{value:"synthetic-chat"}
    }}});
    await browser.action("discover");
    await browser.action("test");
    assert.equal(browser.isVerified(),true);
    await browser.submit({target:{dataset:{osForm:"bm-chat"},elements:{
      prompt:{value:"Analyze evidence"},record_id:{value:"public-1"}
    }}});
    const rendered=browser.render("ai");
    assert.match(rendered,/Synthetic local reply/);
    const requests=calls.filter(x=>x.options.method==="POST");
    assert.equal(requests.length,2);
    assert.ok(requests.every(x=>x.options.credentials==="omit"));
    assert.ok(requests.every(x=>x.url.startsWith("http://127.0.0.1:11434/v1/")));
    assert.match(requests[1].options.body,/Public opportunity/);
    assert.ok(!requests.some(x=>Object.keys(x.options.headers||{}).some(k=>/authorization/i.test(k))));
    assert.equal(notices.length,0);
  } finally {
    for (const [key,value] of Object.entries(old)) {
      if (value === undefined) delete globalThis[key];
      else globalThis[key]=value;
    }
  }
});
