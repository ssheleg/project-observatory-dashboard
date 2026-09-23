/* Offline behavior checks for the public site's clipboard and example controls. */
const {readFileSync} = require('node:fs');
const {resolve} = require('node:path');
const vm = require('node:vm');
const assert = require('node:assert/strict');
const root = resolve(__dirname, '..');
const html = readFileSync(resolve(root, 'site/index.html'), 'utf8');
const promptText = html.match(/<pre id="agent-prompt"[^>]*>([\s\S]*?)<\/pre>/)[1];
function setup(clipboard) {
  const nodes = {};
  for (const id of ['sample-before','sample-after','copy-prompt','agent-prompt','copy-status','prompt-details']) {
    nodes['#'+id] = {hidden:false, disabled:false, textContent:id==='agent-prompt'?promptText:'',
      addEventListener(_,fn){this.click=fn;}, focus(){this.focused=true;}};
  }
  const controls = ['before','after'].map(state=>({dataset:{state},addEventListener(_,fn){this.click=fn;},setAttribute(k,v){this[k]=v;}}));
  const selection={removeAllRanges(){},addRange(range){this.range=range;}};
  vm.runInNewContext(readFileSync(resolve(root,'site/app.js'),'utf8'),{
    document:{querySelector:s=>nodes[s],querySelectorAll:()=>controls,createRange:()=>({selectNodeContents(node){this.node=node;}})},
    navigator:{clipboard},window:{getSelection:()=>selection}
  });
  return {nodes,controls,selection};
}
(async()=>{
  let written, release;
  const pending = new Promise(r=>release=r);
  const good=setup({writeText:async value=>{written=value;await pending;}});
  const copying=good.nodes['#copy-prompt'].click();
  assert.equal(good.nodes['#copy-prompt'].disabled,true);
  release();await copying;
  assert.equal(written,promptText);
  assert.match(written,/github.com\/ssheleg\/project-observatory-dashboard/);
  assert.equal(good.nodes['#copy-prompt'].disabled,false);
  assert.match(good.nodes['#copy-status'].textContent,/Copied/);
  await good.nodes['#copy-prompt'].click();
  good.controls[1].click();
  assert.equal(good.nodes['#sample-before'].hidden,true);
  assert.equal(good.nodes['#sample-after'].hidden,false);
  good.controls[0].click();
  assert.equal(good.nodes['#sample-after'].hidden,true);
  for(const clipboard of [undefined,{writeText:async()=>{throw new Error('permission denied');}}]){
    const bad=setup(clipboard);await bad.nodes['#copy-prompt'].click();
    assert.equal(bad.nodes['#prompt-details'].open,true);
    assert.equal(bad.nodes['#agent-prompt'].focused,true);
    assert.equal(bad.selection.range.node,bad.nodes['#agent-prompt']);
    assert.equal(bad.nodes['#copy-prompt'].disabled,false);
    assert.match(bad.nodes['#copy-status'].textContent,/copy it with your keyboard/);
  }
  assert.match(html,/<details id="prompt-details">[\s\S]*<summary>Read the setup prompt<\/summary>/);
  console.log('PASS: exact prompt payload, pending/retry, clipboard denial/absence recovery, example toggle, static disclosure');
})().catch(error=>{console.error(error);process.exitCode=1;});
