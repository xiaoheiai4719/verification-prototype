// Offline DOM harness checking the generated page's exact inline JS.
// This is not a visual or native browser test. Run: node tests/check_lesson_ui.cjs
'use strict';
const {readFileSync}=require('node:fs');
const vm=require('node:vm');
const assert=require('node:assert/strict');
const path=require('node:path');
const html=readFileSync(path.join(__dirname,'../outputs/demo/learn.html'),'utf8');
const payload=html.match(/<script type="application\/json" id="lesson-data">([\s\S]*?)<\/script>/)[1];
const program=html.match(/<script>([\s\S]*?)<\/script>/)[1];
const create=()=>({
  value:'', textContent:'', hidden:false, disabled:false, events:{}, children:[],
  addEventListener(event,handler){this.events[event]=handler},
  fire(event){this.events[event]({preventDefault(){}})},
  append(child){this.children.push(child)},focus(){this.focused=true}
});
const nodes=Object.fromEntries([...html.matchAll(/<\w+[^>]*?\bid="([^"]+)"[^>]*>/g)].map(([markup,id])=>[id,Object.assign(create(),{hidden:/\shidden[\s>]/.test(markup)})]));
nodes['lesson-data'].textContent=payload;
vm.runInNewContext(program,{document:{getElementById:id=>nodes[id],createElement:create}});
const {answer,second,third,next,reveal,steps,result}=nodes;
assert(second.hidden&&third.hidden);
answer.value='  ';
nodes['answer-form'].fire('submit');
assert(second.hidden);
answer.value='保留最初的思路';
nodes['answer-form'].fire('submit');
assert(!second.hidden&&third.hidden);
next.fire('click');assert.equal(steps.children.length,1);
next.fire('click');assert.equal(steps.children.length,2);assert(next.disabled&&third.hidden);
next.fire('click');assert.equal(steps.children.length,2);
answer.value='修改后的思路';nodes['answer-form'].fire('submit');
reveal.fire('click');assert(!third.hidden&&reveal.disabled);
const text=n=>n.textContent+n.children.map(text).join('\n');
assert.match(text(result),/保留最初的思路/);
assert.match(text(result),/原版：失败，实际保存 2 个对象/);
assert.match(text(result),/对照修正版：通过，实际保存 1 个对象/);
assert.match(text(result),/仍未验证/);
assert.match(text(result),/def put/);
console.log('Offline lesson JS: first answer, sequential hints, source and measured results PASS');
