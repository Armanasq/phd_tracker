export async function consumeAgentStream(response,{onDelta,signal}={}) {
  if (!response?.ok) throw new Error("Streaming request was rejected");
  if (!response.headers.get("content-type")?.toLowerCase().includes("text/event-stream")) {
    throw new Error("Private runtime did not return SSE");
  }
  if (!response.body) throw new Error("Streaming body unavailable");
  const reader=response.body.getReader();
  const decoder=new TextDecoder("utf-8",{fatal:true});
  let pending="",total=0,content="",result=null,done=false;
  const handle=block=>{
    let type="message",payload=[];
    for(const line of block.split("\n")) {
      if(line.startsWith("event:"))type=line.slice(6).trim();
      else if(line.startsWith("data:"))payload.push(line.slice(5).trimStart());
    }
    if(!payload.length)return;
    let value;
    try{value=JSON.parse(payload.join("\n"));}
    catch{throw new Error("Invalid private SSE payload");}
    if(type==="delta"){
      if(typeof value.text!=="string")throw new Error("Invalid SSE text delta");
      content+=value.text;
      if(content.length>20000)throw new Error("SSE response exceeded 20,000 characters");
      onDelta?.(content);
    }else if(type==="result"){
      if(!value||typeof value.text!=="string")throw new Error("Missing structured SSE result");
      result=value;
    }else if(type==="error"){
      throw new Error(String(value.error||"Private inference failed").slice(0,200));
    }else if(type==="done"){
      done=value.status==="complete";
    }
  };
  try{
    while(true){
      if(signal?.aborted)throw new DOMException("Aborted","AbortError");
      const {value,done:finished}=await reader.read();
      if(finished)break;
      total+=value.byteLength;
      if(total>2_000_000)throw new Error("Private SSE response exceeded 2 MB");
      pending+=decoder.decode(value,{stream:true}).replace(/\r\n/g,"\n");
      if(pending.length>200000)throw new Error("Oversized private SSE frame");
      let end;
      while((end=pending.indexOf("\n\n"))!==-1){
        handle(pending.slice(0,end));
        pending=pending.slice(end+2);
      }
    }
    pending+=decoder.decode();
    if(pending.trim())handle(pending);
    if(!done||!result||result.text!==content)throw new Error("Private SSE terminated without a consistent final result");
    return result;
  }finally{
    await reader.cancel().catch(()=>{});
    reader.releaseLock();
  }
}
