'use strict';
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const {pathToFileURL}=require('node:url');
const {chromium}=require('playwright');

(async()=>{
  const artifacts=path.resolve('artifacts','ui-qa');
  fs.mkdirSync(artifacts,{recursive:true});
  const browser=await chromium.launch({headless:true,args:['--no-sandbox']});
  const errors=[];
  try{
    const page=await browser.newPage({viewport:{width:1600,height:1000},deviceScaleFactor:1});
    page.on('pageerror',error=>errors.push(error.message));
    await page.goto(pathToFileURL(path.resolve('dashboard/index.html')).href,{waitUntil:'load'});
    await page.locator('#lab-sankey').waitFor();
    assert.equal(await page.locator('.stat').count(),6);
    assert.ok(await page.locator('#lab-sankey rect[role="button"]').count()>0);
    assert.ok(await page.locator('#lab-timeline circle[role="button"]').count()>0);
    assert.ok(await page.locator('#lab-quadrant-viz circle[role="button"]').count()>0);
    assert.ok(await page.locator('#lab-world circle[role="button"]').count()>0);
    assert.ok(await page.locator('#lab-research-viz circle[role="button"]').count()>0);
    assert.ok(await page.locator('#priority-list .priority-item').count()>0);
    await page.screenshot({path:path.join(artifacts,'desktop-overview.png'),fullPage:true});
    const select=page.locator('#lab-country');
    assert.ok(await select.locator('option').count()>1);
    await select.selectOption({index:1});
    assert.match(await page.locator('#lab-map-info').innerText(),/mapped records/i);
    await page.locator('#pipeline-steps button').nth(1).click();
    assert.match(await page.locator('#pipeline-status').innerText(),/VERIFY/);
    await page.locator('#lab-timeline circle[role="button"]').first().click();
    assert.ok((await page.locator('#detail-body').innerText()).length>10);
    await page.locator('#chronos').evaluate(el=>{
      el.value='30';
      el.dispatchEvent(new Event('input',{bubbles:true}));
    });
    assert.match(await page.locator('#chronos-date').innerText(),/30 days/);
    await page.locator('#weight-proof').evaluate(el=>{
      el.value='8';
      el.dispatchEvent(new Event('input',{bubbles:true}));
    });
    assert.equal(await page.locator('#out-proof').innerText(),'8');
    await page.keyboard.press('Control+k');
    assert.equal(await page.locator('#command-shade').getAttribute('aria-hidden'),'false');
    await page.keyboard.press('Escape');
    assert.equal(await page.locator('#command-shade').getAttribute('aria-hidden'),'true');
    await page.setViewportSize({width:390,height:844});
    await page.screenshot({path:path.join(artifacts,'mobile-overview.png'),fullPage:true});
    if(errors.length)throw new Error('Browser runtime errors:\n'+errors.join('\n'));
    console.log(JSON.stringify({status:'pass',cards:6,mapOptions:await select.locator('option').count(),screenshots:['desktop-overview.png','mobile-overview.png']}));
    await page.close();
  }finally{
    await browser.close();
  }
})().catch(error=>{console.error(error);process.exitCode=1;});
