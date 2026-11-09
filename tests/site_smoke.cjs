'use strict';
const assert = require('node:assert/strict');
const http = require('node:http');
const fs = require('node:fs/promises');
const path = require('node:path');
const {chromium} = require('playwright');

async function run() {
  const site = path.resolve('site');
  const out = path.resolve('artifacts', 'ui-qa');
  await fs.mkdir(out, {recursive:true});
  const server = http.createServer(async (req, res) => {
    try {
      const raw = decodeURIComponent(new URL(req.url, 'http://127.0.0.1').pathname);
      const name = raw === '/' ? '/index.html' : raw;
      const full = path.resolve(site, '.' + name);
      if (!full.startsWith(site + path.sep)) {res.writeHead(403);res.end();return}
      const body = await fs.readFile(full);
      const type = (full.endsWith('.js') || full.endsWith('.mjs')) ? 'application/javascript' : full.endsWith('.css') ? 'text/css' : full.endsWith('.json') ? 'application/json' : 'text/html';
      res.writeHead(200, {'Content-Type':type+'; charset=utf-8'});
      res.end(body);
    } catch {
      res.writeHead(404);
      res.end('Not found');
    }
  });
  await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));
  const base = 'http://127.0.0.1:'+server.address().port;
  const browser = await chromium.launch({headless:true,args:['--no-sandbox']});
  const errors = [];
  const page = await browser.newPage({viewport:{width:1512,height:982},acceptDownloads:true});
  page.on('pageerror',error=>errors.push(error.message));
  page.on('console',msg=>{if(msg.type()==='error')console.error('[browser console]',msg.text())});
  page.on('requestfailed',req=>console.error('[browser failed]',req.url(),req.failure()));
  page.on('response',res=>{if(res.status()>=400)console.error('[HTTP]',res.status(),res.url())});
  try {
    const response = await page.goto(base+'/',{waitUntil:'networkidle'});
    assert.equal(response.status(),200);
    await page.locator('#body h1').waitFor({timeout:7500}).catch(async err=>{console.error('[bootstrap]',await page.locator('#body').innerHTML(),errors);throw err});
    assert.match(await page.locator('#body h1').innerText(),/Today’s work/);
    assert.equal(await page.locator('.kpi').count(),5);
    assert.match(await page.locator('.kpi').first().innerText(),/Tracked applications\s*109/);
    assert.equal(await page.locator('body').evaluate(el=>getComputedStyle(el).backgroundColor),'rgb(250, 249, 246)');
    assert.ok((await page.locator('.agenda-item').count())>=5);
    assert.ok((await page.locator('.nav-btn').count())>=11);
    await page.screenshot({path:path.join(out,'phd-atlas-desktop.png'),fullPage:true});

    await page.locator('#navigation [data-action="nav"][data-value="calendar"]').click();
    assert.match(await page.locator('#body h1').innerText(),/Application calendar/);
    assert.ok((await page.locator('.cal-day').count())>=28);
    await page.locator('[data-action="cal-next"]').click();
    assert.ok((await page.locator('.cal-day').count())>=28);

    await page.locator('#navigation [data-action="nav"][data-value="applications"]').click();
    assert.ok((await page.locator('tbody tr').count())>=100);
    await page.locator('#filterQuery').fill('N263-05');
    assert.equal(await page.locator('tbody tr').count(),1);
    await page.locator('#filterQuery').fill('');
    await page.locator('#filterScope').selectOption('candidate');
    assert.equal(await page.locator('#body .count').innerText().then(s=>s.includes('21 records')),true);
    await page.locator('[data-action="save-view"]').click();
    await page.locator('#viewName').fill('Candidates to review');
    await page.locator('[data-action="confirm-view"]').click();
    assert.equal(await page.locator('#viewPreset').inputValue(),'Candidates to review');
    await page.locator('[data-action="clear-filters"]').click();
    assert.equal(await page.locator('#filterScope').inputValue(),'tracked');
    await page.locator('#viewPreset').selectOption('Candidates to review');
    assert.equal(await page.locator('#filterScope').inputValue(),'candidate');
    await page.reload({waitUntil:'networkidle'});
    await page.locator('#body h1').waitFor();
    assert.equal(await page.locator('#filterScope').inputValue(),'candidate');
    await page.locator('[data-action="clear-filters"]').click();
    await page.locator('[data-compare]').nth(0).check();
    await page.locator('[data-compare]').nth(1).check();
    assert.match(await page.locator('#body [data-action="nav"][data-value="compare"]').innerText(),/Compare selected \(2\)/);
    await page.locator('#navigation [data-action="nav"][data-value="compare"]').click();
    assert.equal(await page.locator('.compare-card').count(),2);

    await page.locator('#navigation [data-action="nav"][data-value="pipeline"]').click();
    assert.equal(await page.locator('.kanban-lane').count(),7);
    assert.ok((await page.locator('[data-stage-id]').count())>0);
    const keyboardStage=page.locator('.kanban-lane[data-lane="unconfirmed"] [data-stage-id]').first();
    await keyboardStage.selectOption('shortlisted');
    assert.ok((await page.locator('.kanban-lane[data-lane="shortlisted"] .kanban-card').count())>=1);
    const before = await page.locator('.kanban-lane[data-lane="shortlisted"] .kanban-card').count();
    await page.locator('.kanban-lane[data-lane="unconfirmed"] .kanban-card').first().dragTo(page.locator('.kanban-lane[data-lane="shortlisted"]'));
    assert.equal(await page.locator('.kanban-lane[data-lane="shortlisted"] .kanban-card').count(),before+1);

    await page.locator('#navigation [data-action="nav"][data-value="updates"]').click();
    assert.ok((await page.locator('#body').innerText()).includes('Local change register'));

    await page.locator('#navigation [data-action="nav"][data-value="applications"]').click();
    const first = page.locator('tbody .rowbutton').first();
    const editedId = await first.getAttribute('data-value');
    await first.click();
    assert.equal(await page.locator('.modal [data-document]').count()>0,true);
    await page.locator('#editNotes').fill('Local QA draft only, not a confirmed application submission');
    await page.locator('[data-action="save-record"]').click();
    assert.equal(await page.locator('.modal').count(),0);
    await page.locator('#navigation [data-value="updates"]').click();
    assert.ok((await page.locator('#body').innerText()).includes('Local draft'));
    await page.locator('[data-action="command"][data-value="'+editedId+'"]').click();
    const publicCommand = await page.locator('.command').innerText();
    assert.ok(!publicCommand.includes('Local QA draft only'), 'Private notes must not enter GitHub commands');
    assert.ok(publicCommand.includes('expected_updated_at'), 'Optimistic source precondition must be carried');
    await page.keyboard.press('Escape');
    await page.locator('#navigation [data-value="applications"]').click();
    const [download] = await Promise.all([
      page.waitForEvent('download'),
      page.locator('[data-action="export"][data-value="csv"]').first().click(),
    ]);
    assert.match(download.suggestedFilename(),/applications\.csv/);

    await page.keyboard.press('Control+k');
    assert.equal(await page.locator('#paletteQuery').count(),1);
    await page.locator('#paletteQuery').fill('N263-05');
    assert.ok((await page.locator('#paletteResults .mini-row').count())>=1);
    await page.keyboard.press('Escape');
    assert.equal(await page.locator('.modal').count(),0);

    const mobile = await browser.newPage({viewport:{width:390,height:844},deviceScaleFactor:1});
    mobile.on('pageerror',error=>errors.push(error.message));
    await mobile.goto(base+'/',{waitUntil:'networkidle'});
    await mobile.locator('#body h1').waitFor();
    await mobile.screenshot({path:path.join(out,'phd-atlas-mobile.png'),fullPage:true});
    await mobile.locator('#navigation [data-action="nav"][data-value="calendar"]').click();
    assert.ok((await mobile.locator('.cal-day').count())>=28);
    await mobile.locator('#navigation [data-action="nav"][data-value="applications"]').click();
    assert.ok((await mobile.locator('tbody tr').count())>=100);
    assert.ok((await mobile.locator('.app-card:visible').count())>=100);
    assert.equal(await mobile.locator('.desktop-table:visible').count(),0);
    await mobile.locator('.app-card .rowbutton').first().click();
    assert.equal(await mobile.locator('.modal [data-document]').count()>0,true);
    await mobile.keyboard.press('Escape');

    const mobileOverflow=await mobile.evaluate(()=>document.documentElement.scrollWidth-document.documentElement.clientWidth);
    assert.ok(mobileOverflow<=2, 'Mobile page must not overflow: '+mobileOverflow+'px');
    await mobile.screenshot({path:path.join(out,'phd-atlas-mobile-applications.png'),fullPage:false});
    await mobile.close();
    for(const [label,width,height] of [['laptop',1280,800],['tablet',820,1180],['narrow',320,700]]){
      const screen=await browser.newPage({viewport:{width,height},deviceScaleFactor:1});
      screen.on('pageerror',error=>errors.push(error.message));
      await screen.goto(base+'/',{waitUntil:'networkidle'});
      await screen.locator('#body h1').waitFor();
      await screen.screenshot({path:path.join(out,'phd-atlas-'+label+'.png'),fullPage:false});
      await screen.locator('#navigation [data-value="applications"]').click();
      const overflow=await screen.evaluate(()=>document.documentElement.scrollWidth-document.documentElement.clientWidth);
      assert.ok(overflow<=2,label+' overflow: '+overflow+'px');
      await screen.close();
    }
    const bad=await browser.newPage({viewport:{width:1024,height:768}});
    bad.on('pageerror',error=>errors.push(error.message));
    await bad.route('**/data/workspace.json',route=>route.fulfill({status:200,contentType:'application/json',body:JSON.stringify({schema_version:1,providers:[],records:[{id:'broken'}]})}));
    await bad.goto(base+'/',{waitUntil:'networkidle'});
    assert.match(await bad.locator('#body h1').innerText(),/Source unavailable/);
    assert.ok((await bad.locator('[data-action="retry-load"]').count())===1);
    await bad.unroute('**/data/workspace.json');
    await bad.locator('[data-action="retry-load"]').click();
    await bad.locator('.agenda-item').first().waitFor();
    await bad.close();

    assert.deepEqual(errors,[]);
    console.log(JSON.stringify({
      status:'pass',
      applicationRows:'100+',
      checked:['dashboard','calendar','applications','saved views','scope','compare','pipeline','accessible status select','drag and draft','source preconditions','editing','export','search','schema-recovery','mobile','tablet','narrow'],
      screenshots:['phd-atlas-desktop.png','phd-atlas-mobile.png']
    }));
  } finally {
    await page.close();
    await browser.close();
    await new Promise(resolve=>server.close(resolve));
  }
}
run().catch(error=>{console.error(error);process.exitCode=1});
