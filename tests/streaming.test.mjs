import test from "node:test";
import assert from "node:assert/strict";
import {consumeAgentStream} from "../site/modules/sse-client.mjs";

function response(frames) {
  const encoder=new TextEncoder();
  return new Response(new ReadableStream({
    start(controller){for(const frame of frames)controller.enqueue(encoder.encode(frame));controller.close();}
  }),{headers:{"Content-Type":"text/event-stream"}});
}

test("private SSE client assembles incremental deltas and validates final response",async()=>{
  const parts=[];
  const result={text:"Evidence remains unverified",model:"local",id:"run-1"};
  const frames=[
    'event: status\ndata: {"status":"running"}\n\n',
    'event: delta\ndata: {"text":"Evidence "}\n\n',
    'event: delta\ndata: {"text":"remains unverified"}\n\n',
    'event: result\ndata: '+JSON.stringify(result)+'\n\n',
    'event: done\ndata: {"status":"complete"}\n\n'
  ];
  const data=await consumeAgentStream(response(frames),{onDelta:x=>parts.push(x)});
  assert.deepEqual(parts,["Evidence ","Evidence remains unverified"]);
  assert.deepEqual(data,result);
});

test("truncated SSE never manufactures a successful result",async()=>{
  await assert.rejects(()=>consumeAgentStream(response([
    'event: delta\ndata: {"text":"partial"}\n\n'
  ])),/consistent final result/);
});

test("mismatched final output is rejected",async()=>{
  await assert.rejects(()=>consumeAgentStream(response([
    'event: delta\ndata: {"text":"actual"}\n\n',
    'event: result\ndata: {"text":"fabricated"}\n\n',
    'event: done\ndata: {"status":"complete"}\n\n'
  ])),/consistent final result/);
});

test("server-side error events are surfaced without creating a completed response",async()=>{
  await assert.rejects(()=>consumeAgentStream(response([
    'event: error\ndata: {"error":"Inference rejected"}\n\n'
  ])),/Inference rejected/);
});

test("non-SSE JSON is not silently treated as streaming",async()=>{
  await assert.rejects(()=>consumeAgentStream(new Response('{"text":"done"}',{
    headers:{"Content-Type":"application/json"}
  })),/did not return SSE/);
});
