export function runtimeCapabilities({privateConnected=false,privateModelVerified=false,browserModelVerified=false}={}) {
  const mode=privateConnected?"private":browserModelVerified?"browser-local":"static";
  const capabilities=[
    {id:"public_evidence",label:"Source-backed tracker",available:true,reason:"Public committed evidence and browser-local records"},
    {id:"direct_chat",label:"Interactive model inference",available:privateConnected?privateModelVerified:browserModelVerified,reason:privateConnected?"Verify a provider in private Settings":browserModelVerified?"Verified browser-to-loopback model":"Connect and probe a local model in Settings"},
    {id:"private_state",label:"Private applicant database",available:privateConnected,reason:privateConnected?"Single-owner SQLite runtime":"Requires the private Python service"},
    {id:"agents",label:"Deterministic tools and agents",available:privateConnected,reason:privateConnected?"Private runtime configured; active model may still require verification":"Requires the private Python service"},
    {id:"automations",label:"Scheduled workflow execution",available:privateConnected,reason:privateConnected?"Requires enabled workflow, running scheduler, consent and quotas":"Requires the private Python service"},
    {id:"cloud_batch",label:"GitHub Actions cloud jobs",available:false,reason:"Optional repository workflow; enable and verify independently in your fork"},
    {id:"cloud_hosted",label:"Authenticated cloud full stack",available:false,reason:"Not implemented; no public API or login is exposed"}
  ];
  return {mode,capabilities,available:capabilities.filter(c=>c.available).map(c=>c.id),blocked:capabilities.filter(c=>!c.available).map(c=>c.id)};
}
