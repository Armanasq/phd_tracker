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
      const type = full.endsWith('.js') ? 'application/javascript' : full.endsWith('.css') ? 'text/css' : full.endsWith('.json') ? 'application/json' : 'text/html';
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
  try {
    const response = await page.goto(base+'/',{waitUntil:'networkidle'});
    assert.equal(response.status(),200);
    await page.locator('#body h1').waitFor();
    assert.match(await page.locator('#body h1').innerText(),/Application command center/);
    assert.equal(await page.locator('.kpi').count(),5);
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
    await page.locator('[data-compare]').nth(0).check();
    await page.locator('[data-compare]').nth(1).check();
    assert.match(await page.locator('#body [data-action="nav"][data-value="compare"]').innerText(),/Compare selected \(2\)/);
    await page.locator('#navigation [data-action="nav"][data-value="compare"]').click();
    assert.equal(await page.locator('.compare-card').count(),2);

    await page.locator('#navigation [data-action="nav"][data-value="pipeline"]').click();
    assert.equal(await page.locator('.kanban-lane').count(),7);
    const before = await page.locator('.kanban-lane[data-lane="shortlisted"] .kanban-card').count();
    await page.locator('.kanban-lane[data-lane="unconfirmed"] .kanban-card').first().dragTo(page.locator('.kanban-lane[data-lane="shortlisted"]'));
    assert.equal(await page.locator('.kanban-lane[data-lane="shortlisted"] .kanban-card').count(),before+1);

    await page.locator('#navigation [data-action="nav"][data-value="updates"]').click();
    assert.ok((await page.locator('#body').innerText()).includes('Unsynchronized local records'));

    await page.locator('#navigation [data-action="nav"][data-value="applications"]').click();
    const first = page.locator('tbody .rowbutton').first();
    await first.click();
    assert.equal(await page.locator('.modal [data-document]').count()>0,true);
    await page.locator('#editNotes').fill('Local QA draft only, not a confirmed application submission');
    await page.locator('[data-action="save-record"]').click();
    assert.equal(await page.locator('.modal').count(),0);
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
    await mobile.close();

    assert.deepEqual(errors,[]);
    console.log(JSON.stringify({
      status:'pass',
      applicationRows:'100+',
      checked:['dashboard','calendar','applications','filter','compare','pipeline','drag and draft','updates','editing','export','search','mobile'],
      screenshots:['phd-atlas-desktop.png','phd-atlas-mobile.png']
    }));
  } finally {
    await page.close();
    await browser.close();
    await new Promise(resolve=>server.close(resolve));
  }
}
run().catch(error=>{console.error(error);process.exitCode=1});
