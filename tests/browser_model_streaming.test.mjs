import test from "node:test";
import assert from "node:assert/strict";
import {createBrowserModel} from "../site/modules/browser-model.mjs";

test("streamed local model stays in memory and does not persist messages", async () => {
  const previous = {location:globalThis.location, localStorage:globalThis.localStorage,
    document:globalThis.document, fetch:globalThis.fetch};
  const stored = new Map(), called = [], notices = [];
  try {
    globalThis.location = {origin:"https://example.github.io",pathname:"/phd_tracker/"};
    globalThis.localStorage = {
      getItem:key=>stored.get(key)??null,
      setItem:(key,value)=>stored.set(key,value)
    };
    globalThis.document = {getElementById:()=>null,querySelector:()=>null};
    globalThis.fetch = async(url,options) => {
      called.push({url,options});
      if (url.endsWith("/models")) return Response.json({data:[{id:"synthetic-chat"}]});
      if (url.endsWith("/chat/completions")) {
        const payload=JSON.parse(options.body);
        if (!payload.stream) return Response.json({choices:[{message:{content:"ready"}}]});
        const chunks=[
          'data: {"choices":[{"delta":{"content":"Local "}}]}\\n\\n',
          'data: {"choices":[{"delta":{"content":"answer"}}]}\\n\\n',
          'data: {"choices":[],"usage":{"prompt_tokens":12,"completion_tokens":2}}\\n\\n',
          'data: [DONE]\\n\\n'
        ].map(x=>new TextEncoder().encode(x.replaceAll("\\n","\n")));
        return new Response(new ReadableStream({start(controller){for(const item of chunks)controller.enqueue(item);controller.close();}}),
          {headers:{"Content-Type":"text/event-stream"}});
      }
      throw new Error("Unexpected endpoint");
    };
    const client=createBrowserModel({notify:x=>notices.push(x),onChange:()=>{},navigate:()=>{},getSourceRecords:()=>[]});
    await client.submit({target:{dataset:{osForm:"bm-config"},elements:{
      baseUrl:{value:"http://127.0.0.1:8000/v1"},model:{value:"synthetic-chat"},streaming:{checked:true}
    }}});
    await client.action("test");
    assert.equal(client.isVerified(),true);
    await client.submit({target:{dataset:{osForm:"bm-chat"},elements:{
      prompt:{value:"Explain evidence gaps"},record_id:{value:""}
    }}});
    assert.match(client.render("ai"),/Local answer/);
    assert.ok(called.some(x=>x.options.body && JSON.parse(x.options.body).stream === true));
    assert.equal(notices.length,0);
    const saved=[...stored.values()].join("\n");
    assert.ok(!saved.includes("Explain evidence gaps"));
    assert.ok(!saved.includes("Local answer"));
  } finally {
    for(const [name,value] of Object.entries(previous)) {
      if(value===undefined)delete globalThis[name];
      else globalThis[name]=value;
    }
  }
});
