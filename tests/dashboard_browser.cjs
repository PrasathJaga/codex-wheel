const {chromium}=require('playwright');
(async()=>{
 const browser=await chromium.launch({headless:true});
 for(const [name,width] of [['desktop',1440],['mobile',390]]){
  const page=await browser.newPage({viewport:{width,height:1000}});
  await page.goto('file://'+process.cwd()+'/dashboard-output/dashboard.html');
  if(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth))throw Error('Overflow '+name);
  for(const text of ['USD 55.00','USD 110.00','Deterministic execution','inconclusive']){
   if(!(await page.locator('body').innerText()).includes(text))throw Error('Missing '+text);
  }
  await page.screenshot({path:'dashboard-output/'+name+'.png',fullPage:true});
  await page.locator('a[href="#ref-0"]').click();
  await page.locator('#ref-0 summary').click();
  if(!(await page.locator('#ref-0').getAttribute('open')!==null))throw Error('Reference did not open');
  await page.close();
 }
 await browser.close();
 console.log('Desktop and mobile: content, overflow, reference navigation passed');
})().catch(error=>{console.error(error);process.exit(1)});
