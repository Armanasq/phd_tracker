'use strict';
(() => {
  const el = id => document.getElementById(id);
  const E = (tag, text='', className='') => {
    const node = document.createElement(tag);
    node.textContent = String(text);
    if (className) node.className = className;
    return node;
  };
  const add = (parent, tag, text='', cls='') => {
    const node = E(tag,text,cls);
    parent.append(node);
    return node;
  };
  const data = D;
  const apps = entries;
  const docs = resources;
  const resourceMap = new Map(docs.map(d=>[d.id,d]));
  const snapshot = data.as_of;
  const ui = {
    horizon:14, weights:{urgency:7,proof:5,document:3},
    focusedId:null, hoverId:null, zoom:1, offsetX:0, offsetY:0,
    mode:'evidence', playing:false, phase:0, drag:null, graphNodes:[],
    currentGraph:{nodes:[],links:[]}
  };
  const reduced = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  const toast = (message) => {
    const target=el('experience-toast');
    target.textContent=message;
    target.dataset.open='true';
    clearTimeout(toast.timeout);
    toast.timeout=setTimeout(()=>target.dataset.open='false',2700);
  };
  const hashNumber=(s)=>{
    let n=2166136261;
    for(let i=0;i<s.length;i++){n^=s.charCodeAt(i);n=Math.imul(n,16777619)}
    return n>>>0;
  };
  const clamp=(value,min,max)=>Math.max(min,Math.min(max,value));
  const upcoming=()=>apps.filter(a=>a.days>=0&&a.days<=ui.horizon);
  const unknownCount=(a)=>a.documents.filter(id=>resourceMap.get(id)?.state==='unknown'&&!selected.has(id)).length;
  const anomalies=new Map();
  for(const anomaly of data.insights?.source_anomalies||[]){
    const key=String(anomaly.application_id||'');
    anomalies.set(key,(anomalies.get(key)||[]).concat(anomaly));
  }
  const scoreApp=(a)=>{
    const days=Math.max(0,a.days);
    const proofs=a.proof_obligations?.length||0;
    const unknown=unknownCount(a);
    const flags=anomalies.get(a.id)?.length||0;
    return {
      a, days, proofs, unknown, flags,
      score:ui.weights.urgency/(days+1)+ui.weights.proof*(proofs+flags)+ui.weights.document*unknown
    };
  };
  const ranked=()=>upcoming().map(scoreApp).sort((a,b)=>b.score-a.score||a.days-b.days||a.a.id.localeCompare(b.a.id));
  const fmtDay=(d)=>d.toString().padStart(2,'0');
  const srcUrl=a=>a.source&&a.source.startsWith('https://')?a.source:'';
  const setInspector=(node)=>{
    const root=el('graph-inspector');
    root.replaceChildren();
    add(root,'div','EVIDENCE GRAPH / NODE INSPECTOR','eyeline');
    if(!node){
      add(root,'h3','Select a relationship');
      add(root,'p','Drag a node to re-layout the graph. Click any application to inspect its documents, evidence obligations and primary source.','muted');
      add(root,'div','','spark');
      add(root,'p','Time travel changes the displayed network, not the underlying source records.','muted');
      return;
    }
    if(node.kind==='resource'){
      const r=resourceMap.get(node.id);
      add(root,'h3',r?.label||node.id);
      add(root,'div',r?.state||'unknown','big');
      add(root,'p',String(upcoming().filter(a=>a.documents.includes(node.id)).length)+' linked application records within the current horizon.','muted');
      add(root,'div','','spark');
      add(root,'p','A link indicates a document mention, not that the applicant lacks the document.','muted');
    }else{
      const a=node.app;
      add(root,'h3',a.name);
      add(root,'div',a.days+'d','big');
      add(root,'p',a.deadline+' · '+a.decision,'muted');
      add(root,'div','','spark');
      add(root,'p',a.documents.length+' document mentions · '+unknownCount(a)+' with unknown readiness');
      add(root,'p',(a.proof_obligations?.length||0)+' proof obligations · '+(anomalies.get(a.id)?.length||0)+' source-monitor anomalies');
      const btn=add(root,'button','Inspect complete record');
      btn.type='button';
      btn.addEventListener('click',()=>{inspect(a);el('details').scrollIntoView({behavior:reduced?'auto':'smooth',block:'center'});});
      if(srcUrl(a)){const link=add(root,'a','  Primary institutional source');link.href=a.source;link.target='_blank';link.rel='noopener noreferrer';}
    }
  };
  const canvas=el('evidence-graph');
  const ctx=canvas.getContext('2d');
  let width=950,height=485,dpr=1;
  const buildGraph=()=>{
    const visible=upcoming();
    const R=docs.map((r,i)=>({
      id:r.id,kind:'resource',label:r.label,
      x:130+(i%2)*53,y:75+i*55, radius:17,
      color:r.state==='ready'?'#72eccc':r.state==='unknown'?'#ffca92':'#87b5f7'
    }));
    const A=visible.slice(0,65).map((a,i)=>{
      const n=hashNumber(a.id);
      const cols=5;
      return {
        id:a.id,kind:'application',app:a,label:a.name,
        x:382+(i%cols)*119+((n%29)-15),
        y:55+Math.floor(i/cols)*32+((n>>>7)%17-8),
        radius:6+Math.min(8,a.documents.length*1.5),
        color:(anomalies.get(a.id)?.length)?'#ff94ac':a.days<=3?'#ffca92':'#72eccc'
      };
    });
    const previous=new Map(ui.graphNodes.map(n=>[n.kind+':'+n.id,n]));
    ui.graphNodes=[...R,...A].map(n=>{
      const p=previous.get(n.kind+':'+n.id);
      return p?{...n,x:p.x,y:p.y}:n;
    });
    const byId=new Map(R.map(n=>[n.id,n]));
    const links=[];
    for(const n of ui.graphNodes.filter(n=>n.kind==='application')){
      if(ui.mode==='evidence')for(const rid of n.app.documents){
        const r=byId.get(rid);if(r)links.push({from:r,to:n});
      }
    }
    ui.currentGraph={nodes:ui.graphNodes,links};
    el('stage-count').textContent=visible.length.toString();
    el('stage-links').textContent=links.length.toString();
    el('stage-conflicts').textContent=visible.filter(a=>anomalies.get(a.id)?.length).length.toString();
    el('chronos-date').textContent=fmtDay(ui.horizon)+' days';
    el('graph-mode').textContent=ui.mode==='evidence'?'Evidence links':'Conflict lens';
    el('graph-mode').setAttribute('aria-pressed',String(ui.mode==='evidence'));
    renderPriority();
    renderBoard();
  };
  const resize=()=>{
    const b=canvas.getBoundingClientRect();
    width=Math.max(260,b.width);height=Math.max(220,b.height);
    dpr=Math.min(2,window.devicePixelRatio||1);
    canvas.width=Math.round(width*dpr);
    canvas.height=Math.round(height*dpr);
    ctx.setTransform(dpr,0,0,dpr,0,0);
  };
  const scaleX=()=>width/1000*ui.zoom;
  const scaleY=()=>height/485*ui.zoom;
  const worldPoint=(clientX,clientY)=>{
    const b=canvas.getBoundingClientRect();
    return {
      x:(clientX-b.left-ui.offsetX)/scaleX(),
      y:(clientY-b.top-ui.offsetY)/scaleY()
    };
  };
  const nodeAt=(x,y)=>{
    let found=null,distance=Infinity;
    for(const n of ui.graphNodes){
      const d=Math.hypot(n.x-x,n.y-y);
      if(d<n.radius+9&&d<distance){found=n;distance=d}
    }
    return found;
  };
  const bezier=(from,to,t)=>{
    const c1x=from.x+130,c2x=to.x-130;
    const inv=1-t;
    return {
      x:inv*inv*inv*from.x+3*inv*inv*t*c1x+3*inv*t*t*c2x+t*t*t*to.x,
      y:inv*inv*inv*from.y+3*inv*inv*t*from.y+3*inv*t*t*to.y+t*t*t*to.y
    };
  };
  const draw=(timestamp=0)=>{
    if(!ctx)return;
    ctx.setTransform(dpr,0,0,dpr,0,0);
    ctx.clearRect(0,0,width,height);
    ctx.fillStyle='#050e1b';ctx.fillRect(0,0,width,height);
    const grad=ctx.createRadialGradient(width*.56,height*.52,1,width*.56,height*.52,width*.75);
    grad.addColorStop(0,'#17445645');grad.addColorStop(1,'#07111c00');
    ctx.fillStyle=grad;ctx.fillRect(0,0,width,height);
    ctx.save();
    ctx.translate(ui.offsetX,ui.offsetY);
    ctx.scale(scaleX(),scaleY());
    ctx.strokeStyle='#28465a60';ctx.lineWidth=1;
    for(let x=0;x<=1000;x+=50){ctx.beginPath();ctx.moveTo(x,0);ctx.lineTo(x,485);ctx.stroke()}
    for(let y=0;y<=485;y+=50){ctx.beginPath();ctx.moveTo(0,y);ctx.lineTo(1000,y);ctx.stroke()}
    ctx.setLineDash([3,11]);
    ctx.strokeStyle='#78c5cc32';
    ctx.beginPath();ctx.ellipse(620,230,315,195,0,0,2*Math.PI);ctx.stroke();
    ctx.setLineDash([]);
    for(const {from,to} of ui.currentGraph.links){
      const emph=ui.hoverId===from.id||ui.hoverId===to.id||ui.focusedId===to.id;
      ctx.beginPath();ctx.moveTo(from.x,from.y);
      ctx.bezierCurveTo(from.x+130,from.y,to.x-130,to.y,to.x,to.y);
      ctx.strokeStyle=emph?'#a8ffe3c6':'#5699aa45';
      ctx.lineWidth=emph?2.4:1.2;ctx.stroke();
      if(!reduced){
        const t=((timestamp*.00014+hashNumber(from.id+to.id)%1000/1000)%1);
        const p=bezier(from,to,t);
        ctx.beginPath();ctx.arc(p.x,p.y,emph?3:1.8,0,Math.PI*2);
        ctx.fillStyle=emph?'#d7ffed':'#6ac2bb7c';ctx.fill();
      }
    }
    for(const n of ui.graphNodes){
      const active=ui.focusedId===n.id||ui.hoverId===n.id;
      const radius=n.radius*(active?1.18:1);
      ctx.beginPath();ctx.arc(n.x,n.y,radius+7,0,Math.PI*2);
      ctx.fillStyle=active?n.color+'33':n.color+'0c';ctx.fill();
      ctx.beginPath();ctx.arc(n.x,n.y,radius,0,Math.PI*2);
      ctx.fillStyle=n.kind==='resource'?'#11283c':n.color;ctx.fill();
      ctx.strokeStyle=n.color;ctx.lineWidth=active?3:1.4;ctx.stroke();
      if(n.kind==='resource'||active){
        ctx.fillStyle='#d9f5f1';ctx.font=(active?14:12)+'px system-ui';
        ctx.textBaseline='middle';
        ctx.fillText(n.kind==='resource'?n.label:n.app.id,n.x+n.radius+12,n.y,185);
      }
    }
    ctx.fillStyle='#91bbcc';ctx.font='12px system-ui';
    ctx.fillText('DOCUMENT / RESOURCE NODES',16,20);
    ctx.fillText('APPLICATION EVIDENCE',445,20);
    ctx.restore();
    if(!reduced)window.requestAnimationFrame(draw);
  };
  const pointerMove=e=>{
    const p=worldPoint(e.clientX,e.clientY);
    if(ui.drag){
      ui.drag.x=clamp(p.x,35,945);ui.drag.y=clamp(p.y,27,459);
      if(reduced)draw();
      return;
    }
    const n=nodeAt(p.x,p.y);
    if(n?.id!==ui.hoverId){ui.hoverId=n?.id||null;if(n)setInspector(n);else if(!ui.focusedId)setInspector(null);if(reduced)draw()}
    canvas.style.cursor=n?'pointer':'grab';
  };
  canvas.addEventListener('pointerdown',e=>{
    const p=worldPoint(e.clientX,e.clientY),n=nodeAt(p.x,p.y);
    if(n){
      ui.drag=n;ui.focusedId=n.id;
      setInspector(n);
      if(n.kind==='application')inspect(n.app);
      canvas.setPointerCapture(e.pointerId);
    }
  });
  canvas.addEventListener('pointermove',pointerMove);
  canvas.addEventListener('pointerup',()=>{ui.drag=null;});
  canvas.addEventListener('pointercancel',()=>{ui.drag=null;});
  canvas.addEventListener('pointerleave',()=>{if(!ui.drag){ui.hoverId=null;if(reduced)draw()}});
  canvas.addEventListener('wheel',e=>{
    e.preventDefault();
    const scale=e.deltaY>0?.9:1.1;
    ui.zoom=clamp(ui.zoom*scale,.65,2.4);
    if(reduced)draw();
  },{passive:false});
  el('graph-fit').addEventListener('click',()=>{
    ui.zoom=1;ui.offsetX=0;ui.offsetY=0;ui.graphNodes=[];
    buildGraph();if(reduced)draw();
  });
  el('graph-mode').addEventListener('click',()=>{
    ui.mode=ui.mode==='evidence'?'conflicts':'evidence';
    buildGraph();if(reduced)draw();
  });
  let playback=null;
  const setHorizon=(value)=>{
    ui.horizon=clamp(Number(value)||0,0,60);
    el('chronos').value=String(ui.horizon);
    buildGraph();if(reduced)draw();
  };
  el('chronos').addEventListener('input',e=>setHorizon(e.target.value));
  const play=(enabled)=>{
    ui.playing=enabled;
    el('chronos-play').setAttribute('aria-pressed',String(enabled));
    el('chronos-play').textContent=enabled?'Pause sweep':'Play deadline sweep';
    clearInterval(playback);
    if(enabled)playback=setInterval(()=>{
      setHorizon(ui.horizon>=60?0:ui.horizon+1);
      if(document.hidden)play(false);
    },320);
  };
  el('chronos-play').addEventListener('click',()=>play(!ui.playing));
  const focusApp=(a)=>{
    ui.focusedId=a.id;
    if(a.days>ui.horizon&&a.days<=60)setHorizon(a.days);
    inspect(a);
    const n=ui.graphNodes.find(n=>n.id===a.id);if(n)setInspector(n);
    el('flight-deck').scrollIntoView({behavior:reduced?'auto':'smooth',block:'start'});
    if(reduced)draw();
  };
  const download=(filename,value,type)=>{
    const blob=new Blob([value],{type});
    const url=URL.createObjectURL(blob);
    const a=document.createElement('a');
    a.href=url;a.download=filename;
    document.body.append(a);a.click();a.remove();
    setTimeout(()=>URL.revokeObjectURL(url),1000);
  };
  el('export-graph').addEventListener('click',()=>{
    const payload={schema_version:1,snapshot,days:ui.horizon,
      nodes:ui.graphNodes.map(n=>({id:n.id,type:n.kind,x:n.x,y:n.y})),
      relationships:ui.currentGraph.links.map(l=>({document_id:l.from.id,application_id:l.to.id,meaning:'document_mentioned'}))
    };
    download('evidence-network-'+snapshot+'.json',JSON.stringify(payload,null,2),'application/json');
    toast('Graph exported with provenance-preserving relationship semantics.');
  });
  function renderPriority(){
    const root=el('priority-list');
    root.replaceChildren();
    const items=ranked();
    for(const [i,s] of items.slice(0,18).entries()){
      const row=add(root,'div','','priority-item');
      add(row,'div',String(i+1).padStart(2,'0'),'rank');
      const center=add(row,'div');
      const name=add(center,'div',s.a.name,'name');
      const explain=add(center,'div','D-'+s.days+' · '+s.proofs+' proof obligations · '+s.unknown+' unknown document mentions · '+s.flags+' source anomalies','why');
      add(row,'span',s.score.toFixed(2),'score');
      row.tabIndex=0;row.setAttribute('role','button');row.setAttribute('aria-label','Inspect '+s.a.name);
      row.addEventListener('click',()=>focusApp(s.a));
      row.addEventListener('keydown',e=>{if(e.key==='Enter')focusApp(s.a)});
    }
    if(!items.length)add(root,'p','No upcoming application records in this window.','muted');
  }
  for(const [name,id] of [['urgency','weight-urgency'],['proof','weight-proof'],['document','weight-document']]){
    el(id).addEventListener('input',e=>{
      ui.weights[name]=Number(e.target.value);
      el('out-'+name).textContent=String(ui.weights[name]);
      renderPriority();
    });
  }
  el('reset-weights').addEventListener('click',()=>{
    ui.weights={urgency:7,proof:5,document:3};
    for(const name of Object.keys(ui.weights)){
      el('weight-'+name).value=String(ui.weights[name]);
      el('out-'+name).textContent=String(ui.weights[name]);
    }
    renderPriority();
    toast('Decision weights reset.');
  });
  el('export-ranked').addEventListener('click',()=>{
    const header=['source_id','deadline','workload_index','proof_obligations','unknown_documents','source_anomalies','source_url'];
    const csv=[header.join(',')];
    const escape=v=>'"'+String(v??'').replaceAll('"','""')+'"';
    for(const p of ranked())csv.push([p.a.id,p.a.deadline,p.score.toFixed(3),p.proofs,p.unknown,p.flags,p.a.source].map(escape).join(','));
    download('evidence-priorities-'+snapshot+'.csv',csv.join('\n'),'text/csv;charset=utf-8');
  });
  const BOARD_KEY='evidencegraph:v1:local-scenario:'+snapshot;
  let board={};
  try{
    const saved=JSON.parse(localStorage.getItem(BOARD_KEY)||'{}');
    if(saved&&typeof saved==='object'&&!Array.isArray(saved)){
      for(const [key,value] of Object.entries(saved))if(['review','prepare','reviewed'].includes(value))board[key]=value;
    }
  }catch(_){}
  const saveBoard=()=>{
    try{localStorage.setItem(BOARD_KEY,JSON.stringify(board))}catch(_){}
  };
  function renderBoard(){
    const visible=ranked().slice(0,12).map(x=>x.a);
    for(const lane of ['review','prepare','reviewed'])el('lane-'+lane).replaceChildren();
    for(const a of visible){
      const lane=board[a.id]||'review';
      const parent=el('lane-'+lane);
      const card=add(parent,'div','','board-card');
      card.draggable=true;
      card.tabIndex=0;
      card.setAttribute('role','button');
      card.setAttribute('aria-label',a.name+'; press Enter to move to next lane');
      add(card,'strong',a.name);
      add(card,'small',a.id+' · '+a.deadline);
      card.addEventListener('dragstart',e=>e.dataTransfer.setData('text/plain',a.id));
      card.addEventListener('keydown',e=>{
        if(e.key==='Enter'||e.key===' '){
          e.preventDefault();
          const all=['review','prepare','reviewed'];
          board[a.id]=all[(all.indexOf(lane)+1)%all.length];
          saveBoard();renderBoard();
        }
      });
      card.addEventListener('dblclick',()=>focusApp(a));
    }
    for(const lane of ['review','prepare','reviewed'])
      el('count-'+lane).textContent=String(visible.filter(a=>(board[a.id]||'review')===lane).length);
  }
  for(const box of document.querySelectorAll('.board-lane')){
    box.addEventListener('dragover',e=>{e.preventDefault();box.classList.add('drag-over')});
    box.addEventListener('dragleave',()=>box.classList.remove('drag-over'));
    box.addEventListener('drop',e=>{
      e.preventDefault();box.classList.remove('drag-over');
      const id=e.dataTransfer.getData('text/plain');
      if(!apps.some(a=>a.id===id))return;
      board[id]=box.dataset.lane;
      saveBoard();renderBoard();
      toast('Scenario lane updated locally. Application status has not changed.');
    });
  }
  el('board-reset').addEventListener('click',()=>{
    board={};saveBoard();renderBoard();toast('Local scenario board reset.');
  });
  el('board-export').addEventListener('click',()=>{
    download('scenario-board-'+snapshot+'.json',JSON.stringify({schema_version:1,as_of:snapshot,meaning:'local_not_official_status',lanes:board},null,2),'application/json');
  });
  const stateLink=()=>{
    const state=new URLSearchParams();
    state.set('days',String(ui.horizon));
    for(const [name,n] of Object.entries(ui.weights))state.set(name,String(n));
    if(ui.focusedId)state.set('id',ui.focusedId);
    return location.href.split('#')[0]+'#'+state.toString();
  };
  const copyLink=()=>{
    const text=stateLink();
    if(navigator.clipboard?.writeText){
      navigator.clipboard.writeText(text).then(()=>toast('Shareable scenario URL copied.'),()=>fallbackCopy(text));
    }else fallbackCopy(text);
  };
  const fallbackCopy=(value)=>{
    const input=document.createElement('textarea');
    input.value=value;document.body.append(input);input.select();
    document.execCommand('copy');input.remove();
    toast('Scenario URL copied. The data snapshot remains fixed.');
  };
  el('share-view').addEventListener('click',copyLink);
  const applyHash=()=>{
    const p=new URLSearchParams(location.hash.replace(/^#/,''));
    const day=Number(p.get('days'));
    if(p.has('days')&&Number.isFinite(day))ui.horizon=clamp(day,0,60);
    for(const name of Object.keys(ui.weights)){
      const n=Number(p.get(name));
      if(p.has(name)&&Number.isFinite(n))ui.weights[name]=clamp(n,0,10);
      el('weight-'+name).value=String(ui.weights[name]);
      el('out-'+name).textContent=String(ui.weights[name]);
    }
    const id=p.get('id');
    if(id&&apps.some(a=>a.id===id))ui.focusedId=id;
  };
  const commands=[
    {title:'Open evidence network',meta:'Interactive node graph',run:()=>el('flight-deck').scrollIntoView({behavior:'smooth'})},
    {title:'Open decision frontier',meta:'Workload weights',run:()=>el('decision-engine').scrollIntoView({behavior:'smooth'})},
    {title:'Open local scenario board',meta:'Drag and drop',run:()=>el('scenario-board').scrollIntoView({behavior:'smooth'})},
    {title:'Open application explorer',meta:'Search & inspect',run:()=>el('query').focus()},
    {title:'Run GitHub scenario lab',meta:'Native workflow dispatch form',run:()=>window.open('https://github.com/Armanasq/phd_tracker/actions/workflows/experience-lab.yml','_blank','noopener')},
    {title:'Export ranked CSV',meta:'Reproducible workload index',run:()=>el('export-ranked').click()},
    {title:'Copy scenario link',meta:'Time horizon and weights',run:copyLink},
    {title:'Play or pause deadline sweep',meta:'Animated temporal lens',run:()=>play(!ui.playing)}
  ];
  let paletteResults=[],paletteIndex=0;
  const renderPalette=()=>{
    const q=el('command-query').value.toLowerCase().trim();
    const search=[
      ...commands.map((c,i)=>({...c,key:'action-'+i})),
      ...apps.filter(a=>(a.name+' '+a.id).toLowerCase().includes(q)).slice(0,35)
        .map(a=>({key:'app-'+a.id,title:a.name,meta:a.id+' · '+a.deadline,run:()=>focusApp(a)}))
    ];
    paletteResults=q?search.filter(x=>(x.title+' '+x.meta).toLowerCase().includes(q)).slice(0,40):search.slice(0,16);
    paletteIndex=clamp(paletteIndex,0,Math.max(0,paletteResults.length-1));
    const root=el('command-results');root.replaceChildren();
    paletteResults.forEach((item,i)=>{
      const btn=add(root,'button','','command-entry');
      add(btn,'span',item.title);
      add(btn,'small',item.meta);
      btn.type='button';
      if(i===paletteIndex)btn.style.background='#1d4652';
      btn.addEventListener('click',()=>{closePalette();item.run()});
    });
    if(!paletteResults.length)add(root,'p','No matching applications or commands.','muted');
  };
  const openPalette=()=>{
    const shade=el('command-shade');
    shade.setAttribute('aria-hidden','false');
    el('command-query').value='';
    paletteIndex=0;renderPalette();
    el('command-query').focus();
  };
  const closePalette=()=>el('command-shade').setAttribute('aria-hidden','true');
  for(const id of ['command-trigger','palette-fab'])el(id).addEventListener('click',openPalette);
  el('command-close').addEventListener('click',closePalette);
  el('command-shade').addEventListener('click',e=>{if(e.target===el('command-shade'))closePalette()});
  el('command-query').addEventListener('input',()=>{paletteIndex=0;renderPalette()});
  el('command-query').addEventListener('keydown',e=>{
    if(e.key==='ArrowDown'){e.preventDefault();paletteIndex=clamp(paletteIndex+1,0,paletteResults.length-1);renderPalette()}
    if(e.key==='ArrowUp'){e.preventDefault();paletteIndex=clamp(paletteIndex-1,0,paletteResults.length-1);renderPalette()}
    if(e.key==='Enter'&&paletteResults[paletteIndex]){e.preventDefault();const action=paletteResults[paletteIndex];closePalette();action.run()}
  });
  document.addEventListener('keydown',e=>{
    const active=document.activeElement;
    const typing=active&&(/^(INPUT|TEXTAREA|SELECT)$/.test(active.tagName)||active.isContentEditable);
    if((e.ctrlKey||e.metaKey)&&e.key.toLowerCase()==='k'){e.preventDefault();openPalette()}
    else if(e.key==='Escape'&&el('command-shade').getAttribute('aria-hidden')==='false')closePalette();
    else if(e.key==='/'&&!typing&&el('command-shade').getAttribute('aria-hidden')==='true'){e.preventDefault();openPalette()}
    else if(e.code==='Space'&&!typing&&el('command-shade').getAttribute('aria-hidden')==='true'){e.preventDefault();play(!ui.playing)}
  });
  applyHash();
  resize();setHorizon(ui.horizon);
  setInspector(ui.graphNodes.find(n=>n.id===ui.focusedId)||null);
  if(!reduced)requestAnimationFrame(draw);
  else draw();
  window.addEventListener('resize',()=>{resize();if(reduced)draw()});
  window.addEventListener('hashchange',()=>{applyHash();setHorizon(ui.horizon)});
})();
