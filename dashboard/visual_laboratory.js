'use strict';
(() => {
  const data=JSON.parse(document.getElementById('evidence-data').textContent);
  const apps=data.applications||[];
  const research=data.research||[];
  const countries=data.geography?.features||[];
  const root=id=>document.getElementById(id);
  const ns='http://www.w3.org/2000/svg';
  const S=(tag,attributes={},text='')=>{
    const item=document.createElementNS(ns,tag);
    for(const [key,value] of Object.entries(attributes))item.setAttribute(key,String(value));
    if(text)item.textContent=String(text);
    return item;
  };
  const add=(parent,tag,attributes={},text='')=>{
    const item=S(tag,attributes,text);parent.append(item);return item;
  };
  const px=n=>Math.round(n*10)/10;
  const selectApplication=a=>{
    if(typeof window.inspect==='function')window.inspect(a);
    const box=root('details');
    if(box)box.scrollIntoView({behavior:'smooth',block:'center'});
  };
  const activate=(node,fn)=>{
    node.setAttribute('class',((node.getAttribute('class')||'')+' lab-svgnode').trim());
    node.setAttribute('tabindex','0');
    node.setAttribute('role','button');
    node.addEventListener('click',fn);
    node.addEventListener('keydown',event=>{
      if(event.key==='Enter'||event.key===' '){event.preventDefault();fn();}
    });
    return node;
  };
  const svgLabel=(svg,x,y,message,attrs={})=>add(svg,'text',{x,y,fill:'#a5c9db','font-family':'Inter,Arial,sans-serif','font-size':11,...attrs},message);
  const tooltip=(node,text)=>add(node,'title',{},text);
  const updateStats=()=>{
    const stats=root('stats');
    if(!stats)return;
    stats.replaceChildren();
    const health=(data.providers||[]).filter(x=>x.health==='ok').length;
    const values=[
      ['OPPORTUNITIES',data.metrics.tracked,'Dated frontier'],
      ['NEXT 7 DAYS',data.metrics.next_seven_days,'Source deadlines'],
      ['DOCUMENT PROOFS',data.metrics.unknown_document_mentions,'Unknown mentions'],
      ['RESEARCH SIGNALS',data.metrics.research_papers,'Indexed papers'],
      ['HEALTHY SOURCES',health+'/'+data.providers.length,'Observed providers'],
      ['SOURCE CONFLICTS',data.metrics.source_conflicts,'Review flags']
    ];
    values.forEach(([heading,value,description])=>{
      const card=document.createElement('div');card.className='stat';
      const title=document.createElement('span');title.textContent=heading;
      const count=document.createElement('strong');count.textContent=value;
      const sub=document.createElement('small');sub.textContent=description;
      card.append(title,count,sub);stats.append(card);
    });
  };
  updateStats();

  const stages=[
    {name:'DISCOVER',value:(data.providers||[]).reduce((s,p)=>s+p.observed,0),meaning:'Observed source listings in the most recent discovery report, not necessarily unique openings.',path:'../data/discovery_report.json'},
    {name:'VERIFY',value:data.metrics.source_conflicts,meaning:'Recorded source contradictions requiring review. Degraded collectors remain visible.',path:'../data/latest_run.json'},
    {name:'PLAN',value:data.metrics.tracked,meaning:'Applications in the dated portfolio frontier. A record is not a submitted application.',path:'../data/portfolio_frontier.json'},
    {name:'EXECUTE',value:data.metrics.next_seven_days,meaning:'Application deadlines within seven calendar days of the recorded snapshot.',path:'../docs/TODAY.md'}
  ];
  const flow=root('pipeline-steps'),flowInfo=root('pipeline-status');
  const chooseStage=index=>{
    flow.querySelectorAll('button').forEach((button,i)=>button.setAttribute('aria-pressed',String(i===index)));
    const s=stages[index];
    flowInfo.replaceChildren();
    const primary=document.createElement('strong');primary.textContent=s.value+' · '+s.name;
    const detail=document.createElement('p');detail.textContent=s.meaning;
    const link=document.createElement('a');link.textContent='Inspect the evidence source';link.href=s.path;
    flowInfo.append(primary,detail,link);
  };
  stages.forEach((stage,index)=>{
    if(index)flow.append(Object.assign(document.createElement('span'),{className:'linker',textContent:'→'}));
    const button=document.createElement('button');
    button.className='step';button.type='button';
    const number=document.createElement('span');number.className='num';number.textContent=String(stage.value);
    const word=document.createElement('span');word.className='word';word.textContent=stage.name;
    button.append(number,word);
    button.addEventListener('click',()=>chooseStage(index));flow.append(button);
  });
  chooseStage(0);

  const bands=[
    {label:'0–7 days',match:a=>a.days>=0&&a.days<=7,color:'#ff8fac'},
    {label:'8–14 days',match:a=>a.days>=8&&a.days<=14,color:'#ffc98c'},
    {label:'15–30 days',match:a=>a.days>=15&&a.days<=30,color:'#62d6c7'},
    {label:'31–60 days',match:a=>a.days>=31&&a.days<=60,color:'#669fff'},
    {label:'61+ days',match:a=>a.days>=61,color:'#ab8bfa'}
  ];
  const funnel=root('lab-sankey');
  const bins=bands.map(b=>({...b,records:apps.filter(b.match)})).filter(b=>b.records.length);
  const total=bins.reduce((s,b)=>s+b.records.length,0);
  const available=220;
  let cursor=25;
  add(funnel,'rect',{x:18,y:25,width:90,height:available,rx:12,fill:'#6433c5'});
  svgLabel(funnel,31,128,'TRACKED',{fill:'#ffffff','font-size':13,'font-weight':700});
  svgLabel(funnel,51,152,total,{fill:'#e6dfff','font-size':22,'font-weight':800,'text-anchor':'middle'});
  bins.forEach((b,index)=>{
    const height=available*(b.records.length/Math.max(1,total));
    const rectHeight=Math.max(15,height-2);
    const y=cursor;
    const destinationY=25+index*47;
    const color=b.color;
    const opacity=.43+index*.035;
    const stream=add(funnel,'path',{d:'M 108 '+px(y)+' C 225 '+px(y)+', 275 '+destinationY+', 375 '+destinationY+' L 375 '+(destinationY+36)+' C 270 '+(destinationY+36)+', 226 '+px(y+height)+', 108 '+px(y+height)+' Z',fill:color,'fill-opacity':opacity,stroke:'none'});
    tooltip(stream,b.label+': '+b.records.length+' actual application records');
    const rectangle=activate(add(funnel,'rect',{x:375,y:destinationY,width:131,height:36,rx:7,fill:color,'fill-opacity':.9}),()=>{
      let report=root('lab-funnel-result');
      if(!report){report=document.createElement('p');report.id='lab-funnel-result';report.className='lab-hint';root('lab-funnel').append(report);}
      report.textContent=b.records.length+' records in '+b.label+': '+b.records.slice(0,4).map(a=>a.id).join(', ')+(b.records.length>4?' …':'');
      if(b.records.length&&typeof window.inspect==='function')window.inspect(b.records[0]);
    });
    tooltip(rectangle,'Select to inspect '+b.records.length+' applications in '+b.label);
    svgLabel(funnel,387,destinationY+15,b.label,{fill:'#061322','font-size':12,'font-weight':800});
    svgLabel(funnel,387,destinationY+29,b.records.length+' applications',{fill:'#122339','font-size':11});
    cursor+=height;
  });

  const gantt=root('lab-timeline');
  const upcoming=apps.filter(a=>a.days>=0&&a.days<=60).sort((a,b)=>a.days-b.days||a.id.localeCompare(b.id)).slice(0,8);
  add(gantt,'rect',{x:155,y:18,width:355,height:248,rx:8,fill:'#0b1f34'});
  for(let day=0;day<=60;day+=10){
    const x=158+day/60*343;
    add(gantt,'line',{x1:x,y1:39,x2:x,y2:253,stroke:'#426277','stroke-opacity':.55,'stroke-dasharray':day?'4 6':'none'});
    svgLabel(gantt,x,29,day+'d',{'text-anchor':'middle','font-size':10});
  }
  upcoming.forEach((a,index)=>{
    const y=53+index*26, x=158+Math.min(60,a.days)/60*343;
    svgLabel(gantt,3,y+3,(a.id+' '+a.name).slice(0,25),{fill:'#c4dbe7','font-size':10});
    add(gantt,'line',{x1:159,y1:y,x2:x,y2:y,stroke:'#6ba9fc','stroke-width':4,'stroke-linecap':'round','stroke-opacity':.62});
    const dot=activate(add(gantt,'circle',{cx:x,cy:y,r:6.4,fill:a.days<=7?'#ff8fac':'#6ae6c4',stroke:'#fff','stroke-width':1.3}),()=>selectApplication(a));
    tooltip(dot,a.name+' · '+a.deadline+' · source '+a.source);
  });
  if(!upcoming.length)svgLabel(gantt,176,140,'No deadline records in this time window');

  const map=root('lab-world'),choose=root('lab-country'),mapInfo=root('lab-map-info');
  const project=(lon,lat)=>[(lon+180)/360*640,(90-lat)/180*300];
  add(map,'rect',{x:0,y:0,width:640,height:300,fill:'#081d31',rx:10});
  for(let lon=-150;lon<=150;lon+=30){const x=project(lon,0)[0];add(map,'line',{x1:x,y1:0,x2:x,y2:300,stroke:'#234b65','stroke-width':.8,'stroke-dasharray':'3 7'})}
  for(let lat=-60;lat<=60;lat+=30){const y=project(0,lat)[1];add(map,'line',{x1:0,y1:y,x2:640,y2:y,stroke:'#234b65','stroke-width':.8,'stroke-dasharray':'3 7'})}
  const continents=[
    [[-166,65],[-149,60],[-131,51],[-126,40],[-117,32],[-105,21],[-91,17],[-84,10],[-78,9],[-75,25],[-61,46],[-54,54],[-80,66],[-110,74],[-150,73]],
    [[-80,13],[-66,9],[-52,-2],[-35,-9],[-38,-20],[-47,-31],[-55,-45],[-70,-56],[-78,-34],[-81,-8]],
    [[-11,36],[-2,43],[14,45],[23,55],[38,58],[55,52],[67,59],[102,55],[129,49],[152,54],[163,62],[174,51],[151,34],[126,21],[109,12],[95,5],[80,9],[60,22],[48,29],[35,32],[26,37],[9,37],[0,35]],
    [[-16,37],[9,37],[36,28],[50,12],[42,-10],[32,-25],[18,-35],[9,-34],[-1,-18],[-12,3]],
    [[111,-12],[124,-13],[138,-11],[154,-21],[153,-35],[134,-39],[116,-33]],
    [[-50,59],[-38,65],[-40,81],[-53,83],[-61,75]],
    [[44,-13],[50,-13],[50,-26],[44,-25]],
    [[130,32],[142,45],[146,41],[137,33]]
  ];
  continents.forEach(poly=>{
    const coordinates=poly.map(p=>project(p[0],p[1]));
    const d='M '+coordinates.map(p=>px(p[0])+' '+px(p[1])).join(' L ')+' Z';
    add(map,'path',{d,fill:'#174363',stroke:'#326f98','stroke-width':1.2,'stroke-linejoin':'round'});
  });
  const countryList=countries.map(f=>({
    name:f.properties.title.split(':')[0],
    count:f.properties.count,
    lon:f.geometry.coordinates[0],lat:f.geometry.coordinates[1]
  }));
  countryList.sort((a,b)=>b.count-a.count);
  countryList.forEach(item=>{
    const option=document.createElement('option');option.value=item.name;
    option.textContent=item.name+' ('+item.count+')';choose.append(option);
  });
  const mapNodes=[];
  countryList.forEach(item=>{
    const [x,y]=project(item.lon,item.lat);
    const radius=4+Math.sqrt(item.count)*2.8;
    const group=add(map,'g');
    add(group,'circle',{cx:x,cy:y,r:radius+10,fill:'#ab75ff','fill-opacity':.14});
    const circle=activate(add(group,'circle',{cx:x,cy:y,r:radius,fill:item.count>=8?'#e979ff':'#58d2ff',stroke:'#faf4ff','stroke-width':1.2,'fill-opacity':.88}),()=>{
      choose.value=item.name;renderCountry(item.name);
    });
    tooltip(circle,item.name+' · '+item.count+' applications; country-level approximate anchor');
    mapNodes.push({name:item.name,group});
  });
  function renderCountry(name){
    for(const marker of mapNodes)marker.group.setAttribute('opacity',name==='all'||marker.name===name?1:.18);
    const records=name==='all'?apps.filter(a=>a.country):apps.filter(a=>a.country===name);
    mapInfo.textContent=name==='all'
      ?records.length+'/'+apps.length+' application records mapped to inferred countries; points are representative capital locations.'
      :name+' · '+records.length+' mapped records · '+records.slice(0,4).map(a=>a.id).join(', ');
  }
  choose.addEventListener('change',()=>renderCountry(choose.value));
  renderCountry('all');

  const researchPanel=root('lab-research-viz'),researchInfo=root('lab-research-info');
  const topicCounts=new Map();
  research.forEach(p=>{
    const topic=p.topic||'uncategorized';
    if(!topicCounts.has(topic))topicCounts.set(topic,[]);
    topicCounts.get(topic).push(p);
  });
  const topics=[...topicCounts].sort((a,b)=>b[1].length-a[1].length).slice(0,7);
  const center={x:257,y:146};
  for(let r of [55,97,128])add(researchPanel,'circle',{cx:center.x,cy:center.y,r,fill:'none',stroke:'#395878','stroke-dasharray':'3 8'});
  topics.forEach(([topic,items],i)=>{
    const angle=-Math.PI/2+i*2*Math.PI/topics.length;
    const x=center.x+130*Math.cos(angle), y=center.y+110*Math.sin(angle);
    add(researchPanel,'path',{d:'M '+center.x+' '+center.y+' L '+px(x)+' '+px(y),stroke:'#75b8fa','stroke-opacity':.48,'stroke-width':1.6});
    const circle=activate(add(researchPanel,'circle',{cx:x,cy:y,r:16+Math.sqrt(items.length)*2.7,fill:i%2?'#9b65ea':'#27c1d2',stroke:'#d9f8ff','stroke-width':1.2}),()=>{
      researchInfo.replaceChildren();
      const heading=document.createElement('strong');heading.textContent=topic.replaceAll('_',' ')+' · '+items.length+' indexed papers';
      researchInfo.append(heading);
      const list=document.createElement('ul');
      items.slice(0,3).forEach(p=>{
        const li=document.createElement('li');
        if(p.url){const a=document.createElement('a');a.href=p.url;a.target='_blank';a.rel='noopener noreferrer';a.textContent=p.title;li.append(a)}
        else li.textContent=p.title;
        list.append(li);
      });
      researchInfo.append(list);
    });
    tooltip(circle,topic+' · '+items.length+' indexed papers');
    svgLabel(researchPanel,x,y+4,items.length,{fill:'#fff','font-size':13,'font-weight':800,'text-anchor':'middle'});
    svgLabel(researchPanel,x,y+33,topic.replaceAll('_',' ').slice(0,19),{'text-anchor':'middle','font-size':10,fill:'#c7daf0'});
  });
  add(researchPanel,'circle',{cx:center.x,cy:center.y,r:36,fill:'#183c50',stroke:'#b493ff','stroke-width':2});
  svgLabel(researchPanel,center.x,center.y-2,'RESEARCH',{'text-anchor':'middle','font-weight':800,fill:'#f5ebff','font-size':12});
  svgLabel(researchPanel,center.x,center.y+17,research.length+' papers',{'text-anchor':'middle',fill:'#aaf3e7','font-size':11});
  if(!topics.length)researchInfo.textContent='No research papers in snapshot.';

  const quadrant=root('lab-quadrant-viz');
  add(quadrant,'rect',{x:53,y:21,width:441,height:240,rx:5,fill:'#071a2a'});
  add(quadrant,'rect',{x:53,y:21,width:220.5,height:120,fill:'#573051','fill-opacity':.2});
  add(quadrant,'rect',{x:273.5,y:21,width:220.5,height:120,fill:'#2b614b','fill-opacity':.22});
  add(quadrant,'line',{x1:273.5,y1:21,x2:273.5,y2:261,stroke:'#a6c4d4','stroke-dasharray':'5 6'});
  add(quadrant,'line',{x1:53,y1:141,x2:494,y2:141,stroke:'#a6c4d4','stroke-dasharray':'5 6'});
  svgLabel(quadrant,59,36,'BUILD EVIDENCE',{'font-size':10,fill:'#ffca92'});
  svgLabel(quadrant,487,36,'VERIFY NOW',{'font-size':10,fill:'#84edbe','text-anchor':'end'});
  svgLabel(quadrant,59,251,'MONITOR',{'font-size':10,fill:'#9cafc8'});
  svgLabel(quadrant,487,251,'EXECUTE',{'font-size':10,fill:'#80c2f8','text-anchor':'end'});
  svgLabel(quadrant,273,287,'Deadline urgency →',{'font-size':12,fill:'#cee6ef','text-anchor':'middle'});
  const qapps=apps.filter(a=>a.days>=0&&a.days<=90).sort((a,b)=>a.days-b.days).slice(0,35);
  qapps.forEach((a,i)=>{
    const urgency=1-a.days/90;
    const debt=Math.min(1,(a.unknown_documents.length+a.proof_obligations.length)/8);
    const x=53+urgency*441,y=261-debt*240;
    const color=debt>.5?'#ed86db':'#5bcbe7';
    const dot=activate(add(quadrant,'circle',{cx:px(x),cy:px(y),r:5.2,fill:color,stroke:'#eefaff','stroke-width':.7,'fill-opacity':.9}),()=>selectApplication(a));
    tooltip(dot,a.id+' · '+a.days+'d to deadline · '+a.unknown_documents.length+' unknown document mentions · '+a.proof_obligations.length+' obligations');
  });
})();
