export const SETUP_MODES=Object.freeze([
  ["pages","GitHub Pages · public workspace"],
  ["browser-local","Pages + local model"],
  ["actions","GitHub Actions · batch AI"],
  ["private","Private Python or Linux Docker"],
  ["cloud","Authenticated cloud · unavailable"]
]);

const repoPattern=/^[A-Za-z0-9][A-Za-z0-9_.-]{0,99}\/[A-Za-z0-9][A-Za-z0-9_.-]{0,99}$/;
const validModes=new Set(SETUP_MODES.map(([id])=>id));
const esc=value=>String(value??"").replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
const step=(id,title,status,detail)=>({id,title,status,detail});

export function assessOnboarding(snapshot,{mode="pages",privateConnected=false,browserModelVerified=false}={}) {
  if(!snapshot||typeof snapshot!=="object")throw new TypeError("A validated source snapshot is required");
  const selected=validModes.has(mode)?mode:"pages";
  const instance=snapshot.instance||{};
  const repository=typeof instance.repository==="string"&&repoPattern.test(instance.repository)?instance.repository:"";
  const independent=instance.type==="independent";
  const source=instance.data_mode==="source";
  const records=Array.isArray(snapshot.records)?snapshot.records:[];
  const hostedCurrent=snapshot.hosted_ai?.state==="current";
  const steps=[
    step("identity","Repository identity",repository?"observed":"action",
      repository?"Snapshot declares "+repository+"; check that it matches your fork.":"Repository identity missing from the public snapshot."),
    step("data","Public evidence policy",source?"observed":"action",
      source?records.length+" committed public record(s) loaded; institutional facts still require verification.":"Starter mode is intentionally empty. Import your own reviewed source and publish explicitly.")
  ];
  if(selected==="pages") {
    steps.push(step("frontend","Static workspace","observed","This browser loaded the static application. GitHub Pages publishing and external account settings are not independently certified."));
  } else if(selected==="browser-local") {
    steps.push(step("model","Local model inference",browserModelVerified?"verified":"action",
      browserModelVerified?"A real local model inference probe succeeded in this browser session.":"Run an OpenAI-compatible model on loopback, allow this page origin, then verify actual inference in Settings."));
  } else if(selected==="actions") {
    steps.push(step("actions","Hosted batch verification",hostedCurrent?"observed":"action",
      hostedCurrent?"The published snapshot includes a current hosted triage result; verify the Actions run separately.":"Configure a protected Actions environment and its secrets in your own fork; public Pages cannot store cloud keys."));
  } else if(selected==="private") {
    steps.push(step("runtime","Private application runtime",privateConnected?"verified":"action",
      privateConnected?"Private loopback API responded in this browser. Agent execution still depends on models, workers and approval.":"Start the local Python runtime or Linux Docker Compose. Do not expose the loopback server publicly."));
  } else {
    steps.push(step("cloud","Hosted cloud backend","blocked","Not implemented. TLS, OIDC, per-user authorization, tenant isolation, secrets and durable workers are required before enabling this mode."));
  }
  steps.push(step("privacy","Privacy and credential boundary","action",
    "Review public Git history before forking or publishing. Keep applicant documents, API keys and receipts out of GitHub Pages and static exports."));
  return {mode:selected,repository,independent,data_mode:instance.data_mode||"unknown",records:records.length,steps,hostedCurrent};
}

export function renderOnboarding(report) {
  if(!report||!Array.isArray(report.steps))throw new TypeError("Invalid setup assessment");
  const repository=repoPattern.test(report.repository)?report.repository:"";
  const base=repository?"https://github.com/"+repository:"";
  const links=base?'<div class="buttons">'+
    '<a href="'+esc(base+'/actions/workflows/publish-cockpit.yml')+'" target="_blank" rel="noopener noreferrer">Pages publishing workflow</a>'+
    '<a href="'+esc(base+'/settings/secrets/actions')+'" target="_blank" rel="noopener noreferrer">Repository Actions secrets</a>'+
    '<a href="'+esc(base+'/blob/main/docs/SELF_HOSTING.md')+'" target="_blank" rel="noopener noreferrer">Self-hosting guide</a></div>':
    '<p class="info">Repository links are unavailable until the snapshot declares a valid GitHub repository identity.</p>';
  const rows=report.steps.map(item=>
    '<article class="mini-row"><div><strong>'+esc(item.title)+'</strong><small>'+esc(item.detail)+'</small></div>'+
    '<span class="pill '+(item.status==="verified"?"green":"neutral")+'">'+esc(item.status==="verified"?"Verified here":item.status==="observed"?"Observed locally":item.status==="blocked"?"Blocked":"Action needed")+'</span></article>').join("");
  return '<section class="panel"><div class="panel-header"><h2>Choose an execution mode</h2></div>'+
    '<label class="field"><span>Target deployment</span><select class="input" id="onboardingMode" aria-label="Target deployment">'+
    SETUP_MODES.map(([id,label])=>'<option value="'+id+'"'+(id===report.mode?' selected':'')+'>'+esc(label)+'</option>').join("")+'</select></label>'+
    '<p class="subtle">Your selection is saved only in this browser. It does not edit GitHub settings, register a model or deploy a server.</p></section>'+
    '<section class="panel"><div class="panel-header"><h2>Deployment readiness</h2></div><div class="mini-list">'+rows+'</div></section>'+
    '<section class="panel"><div class="panel-header"><h2>Configuration and next actions</h2></div>'+
    '<div class="buttons"><button type="button" class="btn primary" data-action="nav" data-value="settings">Configure model</button>'+
    '<button type="button" class="btn secondary" data-action="nav" data-value="applications">Review public records</button>'+
    '<button type="button" class="btn secondary" data-action="export" data-value="setup">Export nonsecret setup summary</button></div>'+
    links+'<p class="footnote">The summary is not a live deployment certification. GitHub Actions, external providers, university evidence and cloud security must be verified independently.</p></section>';
}
