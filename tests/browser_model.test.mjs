import test from "node:test";
import assert from "node:assert/strict";
import {normalizeLoopbackEndpoint,normalizeModelId,modelText} from "../site/modules/browser-model.mjs";

test("accepts only browser-local HTTP /v1 endpoints", () => {
  assert.equal(normalizeLoopbackEndpoint("http://127.0.0.1:8000/v1"),"http://127.0.0.1:8000/v1");
  assert.equal(normalizeLoopbackEndpoint("http://localhost:11434/v1/"),"http://localhost:11434/v1");
  assert.equal(normalizeLoopbackEndpoint("http://[::1]:8000/v1"),"http://[::1]:8000/v1");
  for (const value of [
    "https://api.openai.com/v1",
    "http://192.168.0.3:8000/v1",
    "http://127.0.0.1.evil.com/v1",
    "http://localhost:70000/v1",
    "http://localhost:11434/v1?key=secret",
    "http://user:pass@localhost:11434/v1",
    "http://localhost:11434/private",
    "http://localhost:11434/v1/../admin",
    "http://2130706433:8000/v1"
  ]) assert.throws(() => normalizeLoopbackEndpoint(value),{name:"Error"});
});

test("requires a valid explicit model identifier", () => {
  assert.equal(normalizeModelId("llama3.2:latest"),"llama3.2:latest");
  assert.equal(normalizeModelId("org/model-7b-instruct"),"org/model-7b-instruct");
  for (const value of ["","model name","../secret?key=abc","x".repeat(161)]) {
    assert.throws(()=>normalizeModelId(value));
  }
});

test("accepts text-only Chat Completions and rejects missing output", () => {
  assert.equal(modelText({choices:[{message:{content:"ready"}}]}),"ready");
  assert.equal(modelText({choices:[{message:{content:[{type:"text",text:"ready"}]}}]}),"ready");
  assert.throws(()=>modelText({choices:[{message:{content:null}}]}));
  assert.equal(modelText({choices:[{message:{content:"a".repeat(25000)}}]}).length,20000);
});
