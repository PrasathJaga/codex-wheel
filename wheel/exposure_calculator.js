/* Integer minor units; explicit user assumptions only. No production frequency inferred. */
(function(root){
 function project(operations, percent, excess){
  if(!/^(0|[1-9][0-9]{0,9})$/.test(operations)||BigInt(operations)>1000000000n)throw Error('Enter whole operations/day from 0 to 1,000,000,000.');
  if(!/^(0|[1-9][0-9]{0,2})(\.[0-9]{1,4})?$/.test(percent))throw Error('Enter an affected percentage from 0 to 100, with at most four decimal places.');
  const [whole,part='']=percent.split('.');const scaled=BigInt(whole)*10000n+BigInt(part.padEnd(4,'0'));
  if(scaled>1000000n)throw Error('Affected percentage must not exceed 100.');
  if(!/^(0|[1-9][0-9]*)$/.test(excess))throw Error('Invalid observed excess.');
  const cents=(BigInt(operations)*scaled*BigInt(excess)+500000n)/1000000n;
  return 'USD '+(cents/100n).toString()+'.'+(cents%100n).toString().padStart(2,'0');
 }
 if(typeof module!=='undefined')module.exports={project};
 else{
  const form=document.getElementById('exposure');
  if(form)form.addEventListener('submit',event=>{
   event.preventDefault();const output=document.getElementById('exposure-result');
   const operations=document.getElementById('operations').value.trim();
   const percent=document.getElementById('affected').value.trim();
   try{output.textContent=operations+' operations/day × '+percent+'% assumed affected × observed excess = '+project(operations,percent,form.dataset.excess)+'/day estimated exposure. Scenario only; not measured loss or guaranteed savings.';}
   catch(error){output.textContent=error.message;}
  });
 }
})(this);
