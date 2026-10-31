const {chromium}=require('playwright');
const fs=require('fs');
(async()=>{
 const browser=await chromium.launch({headless:true});
 const root=process.cwd()+'/two-domain-output';
 for(const [name,width] of [['desktop',1440],['mobile',390]]){
  const page=await browser.newPage({viewport:{width,height:1000}});
  await page.goto('file://'+root+'/dashboard.html');
  if(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth))throw Error('Overflow '+name);
  const text=await page.locator('body').innerText();
  for(const expected of ['USD 40.00','Existing unchanged JUnit already caught','no support-agent conversation is invented','22,763','31,814','15,931'])if(!text.includes(expected))throw Error('Missing '+expected);
  await page.locator('button[data-domain=inventory][data-stage=repaired]').click();
  if(!(await page.locator('[data-panel=inventory-repaired]').isVisible()))throw Error('Inventory repair toggle failed');
  if(!(await page.locator('[data-panel=inventory-repaired]').innerText()).includes('0 orders'))throw Error('Invalid inventory repair count');
  await page.locator('button[data-domain=refund][data-stage=repaired]').click();
  if((await page.locator('[data-panel=refund-repaired]').innerText()).includes('USD 40.00'))throw Error('Refund repair changed amount');
  await page.locator('#operations').fill('10000');await page.locator('#affected').fill('1.6');
  await page.locator('button[type=submit]').click();
  if(!(await page.locator('#exposure-result').innerText()).includes('USD 3200.00/day'))throw Error('Projection wrong');
  await page.locator('#affected').fill('101');await page.locator('button[type=submit]').click();
  if(!(await page.locator('#exposure-result').innerText()).includes('must not exceed'))throw Error('Invalid percentage accepted');
  await page.locator('#inventory-sources summary').click();
  if(!(await page.locator('#inventory-sources').innerText()).includes('InventoryStore.java'))throw Error('Missing source');
  await page.screenshot({path:root+'/'+name+'.png',fullPage:true});
  await page.close();
 }
 const context=await browser.newContext({viewport:{width:1920,height:1080},recordVideo:{dir:root+'/recording',size:{width:1920,height:1080}}});
 const page=await context.newPage();await page.goto('file://'+root+'/dashboard.html');
 const shots=[['overview','#overview'],['refund-before','#refund'],['refund-after','#refund'],['inventory-before','#inventory'],['inventory-after','#inventory'],['repair','#repair'],['limits','#limits']];
 for(const [name,selector] of shots){
  if(name==='refund-after')await page.locator('button[data-domain=refund][data-stage=repaired]').click();
  if(name==='inventory-after')await page.locator('button[data-domain=inventory][data-stage=repaired]').click();
  await page.locator(selector).scrollIntoViewIfNeeded();
  await page.locator(selector).evaluate(el=>el.scrollIntoView({block:'start'}));
  await page.waitForTimeout(800);
  await page.screenshot({path:root+'/scene-'+name+'.png'});
 }
 const video=page.video();await context.close();await video.saveAs(root+'/actual-report.webm');
 await browser.close();console.log('Two-domain desktop/mobile, stage toggles, exact exposure and evidence navigation passed');
})().catch(error=>{console.error(error);process.exit(1)});
