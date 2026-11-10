import {observationLink} from "./source-observations.mjs";

const esc = value=>String(value??"").replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
const TYPES=Object.freeze([["deadline","Deadline"],["eligibility","Eligibility"],["funding","Funding"],["documents","Documents"],["recruitment","Recruitment"],["other","Other"]]);
const knownTypes=new Set(TYPES.map(([value])=>value));

export function claimCandidates(observations=[]) {
  if(!Array.isArray(observations))throw new TypeError("Expected source observations");
  return observations.filter(item=>Number.isSafeInteger(item?.id)&&item.id>0&&Boolean(item.excerpt_available)&&typeof item.source_url==="string")
    .sort((a,b)=>b.id-a.id).slice(0,200);
}

export function renderSourceClaims({observations=[],claims=[],selectedId=null,sourceText=null,diff=null,diffError="",error="",message="",loading=false,filter="all"}={}) {
  if(!Array.isArray(claims))throw new TypeError("Expected captured source claims");
  const candidates=claimCandidates(observations);
  const selected=candidates.find(o=>o.id===selectedId)||candidates[0]||null;
  const text=sourceText?.id===selected?.id&&sourceText?.content_sha256===selected?.content_sha256?sourceText:null;
  const selectedFilter=knownTypes.has(filter)?filter:"all";
  const filtered=claims.filter(c=>selectedFilter==="all"||c.claim_type===selectedFilter);
  const options=candidates.map(o=>'<option value="'+o.id+'"'+(o.id===selected?.id?' selected':'')+'>'+esc(o.application_id)+' · '+esc(o.observed_at||"Unknown time")+' · #'+o.id+'</option>').join("");
  const quoted=text&&typeof text.visible_text==="string"&&text.visible_text.length>0;
  const comparison=diff?.observation_id===selected?.id?diff:null;
  const diffPanel=comparison?'<section class="os-panel"><div class="os-panel-heading"><div><h2>Visible text comparison</h2><p>'+
    esc(comparison.status.replaceAll("_"," "))+' · '+(comparison.comparison_complete?"Captured text compared":"Partial or unavailable comparison")+
    '</p></div></div>'+
    '<p class="os-footnote">Possible review topics: '+esc((comparison.possible_topics||[]).join(", ")||"Not identified")+
    '. These are lexical hints, not verified requirements.</p>'+
    '<div class="os-diff-list">'+(comparison.changes||[]).map(change=>
      '<div class="os-diff-row"><small>'+esc(change.type)+'</small>'+
      '<div class="os-diff-before"><strong>Previous</strong><p>'+esc(change.before||"No text")+'</p></div>'+
      '<div class="os-diff-after"><strong>Current</strong><p>'+esc(change.after||"No text")+'</p></div></div>').join("")+
    ((comparison.changes||[]).length===0?'<p class="os-note">No comparable changes are available for this observation.</p>':'')+
    '</div><p class="os-footnote">'+esc(comparison.notice||"")+'</p></section>':"";
  const capture=quoted?'<form class="os-form" data-os-form="source-claim">'+
    '<input type="hidden" name="observation_id" value="'+selected.id+'">'+
    '<input type="hidden" name="expected_digest" value="'+esc(text.content_sha256)+'">'+
    '<div class="os-form-two">'+
    '<label class="os-field"><span>Claim category</span><select name="claim_type">'+TYPES.map(([id,label])=>'<option value="'+id+'">'+label+'</option>').join("")+'</select></label>'+
    '<label class="os-field"><span>Candidate value (unverified)</span><input name="candidate_value" required maxlength="160" placeholder="e.g. 2026-12-15"></label></div>'+
    '<label class="os-field"><span>Exact quotation from the captured text</span><textarea name="quote" required minlength="20" maxlength="320" rows="3" placeholder="Copy the exact institutional statement here."></textarea></label>'+
    '<div class="os-actions"><button type="button" class="os-btn quiet" data-os-action="use-selected-quote">Use highlighted text</button>'+
    '<button type="submit" class="os-btn primary"'+(loading?' disabled':'')+'>Capture source quote</button></div>'+
    '<p class="os-footnote">The server checks the exact excerpt against the captured text and observation digest. It does not verify that your candidate interpretation is true or update application records.</p></form>':
    '<p class="os-empty">Choose an observed source and load its captured text before recording a quote.</p>';
  const sourcePanel=selected?'<section class="os-panel"><div class="os-panel-heading"><div><h2>Observed source text</h2>'+
      '<p>Captured from a public HTTPS source. Scripts and styles are excluded; dynamically rendered information may be absent.</p></div></div>'+
      '<label class="os-field os-source-selector"><span>Observation</span><select data-os-claim-observation aria-label="Choose source observation">'+options+'</select></label>'+
      '<div class="os-actions"><button type="button" class="os-btn quiet" data-os-action="load-claim-source"'+(loading?' disabled':'')+'>Load captured text</button>'+
      (quoted?'<button type="button" class="os-btn quiet" data-os-action="compare-claim-source"'+(loading?' disabled':'')+'>Compare previous fetch</button>':'')+'</div>'+
      (quoted?'<div class="os-source-sample" id="sourceCapturedText" tabindex="0" aria-label="Captured institutional source text">'+esc(text.visible_text)+'</div>'+
        '<p class="os-footnote">Text hash: '+esc(text.visible_text_sha256)+
        (text.visible_text_truncated?' · Extracted text truncated to the retained prefix; quote matching is limited to that prefix.':'')+'</p>':
        '<p class="os-note">No source excerpt loaded. Captures are owner-only and never published to Pages.</p>')+'</section>':
    '<section class="os-panel"><p class="os-empty">No retained source text. Run a deliberate observation from Source observations, then return here.</p></section>';
  const rows=filtered.slice(0,100).map(item=>{
    const link=observationLink(item.source_url);
    return '<article class="os-ledger-row"><div><strong>'+esc(item.application_id)+' · '+esc(item.claim_type)+'</strong>'+
      '<small>'+esc(item.captured_at)+' · Observation #'+esc(item.observation_id)+'</small>'+
      '<p class="os-evidence-quote">'+esc(item.exact_quote)+'</p>'+
      '<small>Candidate: '+esc(item.candidate_value)+' · Captured quote, factual interpretation unverified</small>'+
      '<small>Owner review: '+esc(({
        needs_recheck:"Needs further review",
        owner_interpretation_supported:"Owner considers the interpretation supported (unverified)",
        owner_interpretation_rejected:"Owner rejected the interpretation"
      })[item.owner_review_decision]||"Not reviewed")+'</small>'+
      (link?'<a href="'+esc(link)+'" target="_blank" rel="noopener noreferrer">Inspect source</a>':'')+
      '<form class="os-form" data-os-form="source-claim-review">'+
      '<input type="hidden" name="claim_id" value="'+esc(item.id)+'">'+
      '<input type="hidden" name="expected_source_digest" value="'+esc(item.source_digest)+'">'+
      '<input type="hidden" name="expected_quote_digest" value="'+esc(item.quote_digest)+'">'+
      '<label class="os-field"><span>Owner interpretation decision</span><select name="decision">'+
      '<option value="needs_recheck">Needs recheck</option>'+
      '<option value="owner_interpretation_supported">Owner considers supported</option>'+
      '<option value="owner_interpretation_rejected">Owner rejects interpretation</option></select></label>'+
      '<label class="os-field"><span>Reasoning and reviewed primary evidence</span>'+
      '<textarea name="rationale" minlength="30" maxlength="1500" required rows="2" placeholder="Describe the evidence, any ambiguity and why this interpretation was accepted or rejected."></textarea></label>'+
      '<button type="submit" class="os-btn quiet"'+(loading?' disabled':'')+'>Record owner decision</button>'+
      '<p class="os-footnote">Append-only owner attestation; no automatic official-fact verification or applicant state changes.</p>'+
      '</form></div></article>';
  }).join("");
  return '<section class="os-page"><div class="os-head"><div><div class="os-kicker">PRIVATE SOURCE PROVENANCE</div>'+
    '<h1>Source evidence</h1><p>Link proposed requirements to exact captured institutional text without fabricating official verification.</p></div>'+
    '<div class="os-head-actions"><button type="button" class="os-btn quiet" data-os-action="go" data-id="source-observations">Source observations</button>'+
    '<button type="button" class="os-btn quiet" data-os-action="refresh-claim-evidence"'+(loading?' disabled':'')+'>Refresh evidence</button></div></div>'+
    (error?'<p class="os-warning" role="alert">'+esc(error)+'</p>':'')+
    (message?'<p class="os-message" role="status">'+esc(message)+'</p>':'')+
    (diffError?'<p class="os-warning" role="alert">'+esc(diffError)+'</p>':'')+
    sourcePanel+diffPanel+
    '<section class="os-panel"><div class="os-panel-heading"><div><h2>Capture a candidate claim</h2>'+
    '<p>The exact quote and content digest become immutable private provenance. No deadline, eligibility, funding or portal state is promoted automatically.</p></div></div>'+
    capture+'</section>'+
    '<section class="os-panel"><div class="os-panel-heading"><div><h2>Captured claims</h2>'+
    '<p>Local SQLite evidence ledger · '+claims.length+' retained record(s). Only the newest 100 matching entries are displayed.</p></div></div>'+
    '<label class="os-field os-source-selector"><span>Claim type</span><select data-os-claim-filter>'+
    '<option value="all"'+(selectedFilter==="all"?' selected':'')+'>All types</option>'+
    TYPES.map(([type,label])=>'<option value="'+type+'"'+(selectedFilter===type?' selected':'')+'>'+label+'</option>').join("")+
    '</select></label><div class="os-ledger">'+(rows||'<p class="os-empty">No captured claims match this filter.</p>')+'</div></section></section>';
}
