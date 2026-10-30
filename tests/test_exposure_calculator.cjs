const assert=require('node:assert/strict');const {project}=require('../wheel/exposure_calculator.js');
assert.equal(project('10000','1.6','5500'),'USD 8800.00');
assert.equal(project('10000','1.6','7500'),'USD 12000.00');
assert.equal(project('0','100','5500'),'USD 0.00');
assert.equal(project('1','50','1'),'USD 0.01');
for(const [n,p] of [['',''],['-1','2'],['1.5','2'],['1','100.1'],['1','NaN'],['1','0.00001'],['1e4','2']])assert.throws(()=>project(n,p,'5500'));
console.log('Exposure arithmetic and invalid-input checks passed');
