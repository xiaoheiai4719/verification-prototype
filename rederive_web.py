"""Standalone offline practice page for one bundled decision card.

The answer is embedded in the HTML for offline use, not security-separated.
Only the browser's normal learner UI reveals it progressively.
"""
import json

def render(report, card):
    import rederive
    session = rederive.start_session(report, card)
    question = rederive.public_view(report, card, session)
    session = rederive.answer(session, '浏览器内另行采集学习者回答')
    steps = []
    for index in range(question['total_hints']):
        session = rederive.hint(report, card, session)
        view = rederive.public_view(report, card, session)
        steps.append(' '.join(part[index] for part in (view['hints'], view['constraints'])
                              if index < len(part)))
    session = rederive.reveal(report, card, session)
    reveal = rederive.public_view(report, card, session)['reveal']
    data = json.dumps({'problem': question['problem'], 'steps': steps, 'reveal': reveal},
                      ensure_ascii=False).replace('<', '\\u003c')
    return PAGE.replace('<!--DATA-->', '<script type="application/json" id="lesson-data">'
                        + data + '</script>')


PAGE = '''<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>设计推演 · 方案与代码核验助手</title>
<style>
:root{color-scheme:light;--ink:#172526;--muted:#4c6161;--edge:#d0dedb;--accent:#0a6354}
*{box-sizing:border-box}body{margin:0;background:#eff5f1;color:var(--ink);font:16px/1.75 system-ui,sans-serif}
main{width:min(100% - 32px,760px);margin:40px auto 72px}header{margin-bottom:22px}h1,h2,h3,p{margin:0 0 12px}
h1{font-size:clamp(28px,5vw,42px);line-height:1.2}h2{font-size:22px}h3{font-size:17px}a{color:var(--accent)}
.kicker{color:var(--accent);font-weight:700;letter-spacing:.09em;font-size:13px}
.card{background:#fff;border:1px solid var(--edge);border-radius:16px;padding:clamp(15px,4vw,30px);margin-bottom:14px}
.muted{color:var(--muted)}label{display:block;font-weight:650}textarea{width:100%;min-height:100px;border:1px solid #758987;border-radius:8px;padding:10px;margin:8px 0;font:inherit;color:inherit}
.actions{display:flex;gap:8px;flex-wrap:wrap}button{font:inherit;font-weight:650;border-radius:8px;border:1px solid var(--accent);background:#fff;color:var(--accent);padding:8px 14px;cursor:pointer}
button.primary{background:var(--accent);color:#fff}button:disabled{opacity:.53;cursor:default}summary{cursor:pointer}
pre{background:#eff5f1;border-radius:8px;padding:12px;white-space:pre-wrap;overflow-wrap:anywhere}
[hidden]{display:none!important}:focus-visible{outline:3px solid #a24d00;outline-offset:4px}
</style></head>
<body><main><header><p class="kicker">方案与代码核验助手 · 离线样例</p>
<h1>先做设计，再看证据</h1><p class="muted">先提交自己的判断，再逐步揭示约束，最后用同一张卡对照源码和测试。</p></header>
<section class="card"><h2>01 · 你会怎么设计？</h2><p id="problem"></p>
<form id="answer-form"><label for="answer">你的设计</label><textarea id="answer" maxlength="4000" required placeholder="写下你的方案，或者写下你现在缺的事实。"></textarea><div class="actions"><button class="primary" type="submit" id="submit">提交思路</button></div></form>
<p id="saved" class="muted" role="status"></p><p class="muted">这页不会给答案打分，也不会把输入发送到任何地方。刷新会清空。</p></section>
<section class="card" id="second" hidden><h2>02 · 加一个约束，再想想</h2><ol id="steps" aria-live="polite"></ol><div class="actions"><button id="next">给我一个提示</button><button id="reveal" class="primary">直接看源码对照</button></div></section>
<section class="card" id="third" hidden><h2 id="third-title" tabindex="-1">03 · 源码和执行结果</h2><div id="result"></div></section>
<p class="muted"><a href="report.html">打开完整核验报告（含答案）</a></p></main>
<!--DATA-->
<script>
'use strict';
const el = id => document.getElementById(id);
const lesson = JSON.parse(el('lesson-data').textContent);
const add = (parent, tag, label) => {
  const node=document.createElement(tag);
  node.textContent=label;
  parent.append(node);
  return node;
};
el('problem').textContent=lesson.problem;
let step=0;
let firstAnswer=null;
el('answer-form').addEventListener('submit', event => {
  event.preventDefault();
  if (!el('answer').value.trim()) { el('saved').textContent='请先写下一句思路，或说明还缺什么信息。'; return; }
  if (firstAnswer===null) firstAnswer=el('answer').value.trim();
  el('saved').textContent=el('second').hidden ? '思路已记录，可以看提示了。' : '已记录修订后的思路，初始回答仍保留。';
  el('submit').textContent='更新思路';
  el('second').hidden=false;
});
el('next').addEventListener('click', () => {
  if (step>=lesson.steps.length) return;
  add(el('steps'),'li',lesson.steps[step++]);
  if (step>=lesson.steps.length) { el('next').disabled=true; el('next').textContent='提示已看完'; }
  else el('next').textContent='再给一个提示';
});
el('reveal').addEventListener('click', () => {
  const reveal=lesson.reveal, root=el('result');
  add(root,'h3','你的首次判断');add(root,'p',firstAnswer);
  add(root,'h3','仓库是怎么做的');add(root,'p',reveal.explanation);
  for (const ref of reveal.references) {
    const details=document.createElement('details');root.append(details);
    add(details,'summary',ref.file+':'+ref.start+'–'+ref.end+' · 看源码');
    add(details,'pre',ref.quote);
  }
  add(root,'h3','设计取舍'); for (const item of reveal.tradeoffs) add(root,'p',item);
  add(root,'h3','验收条件'); for (const item of reveal.acceptance_checks) add(root,'p',item);
  add(root,'h3','执行记录（只对虚构样例有效）');
  const list=document.createElement('ul');root.append(list);
  for (const row of reveal.test_status.runs) {
    const variant={baseline:'原版',fixed:'对照修正版'}[row.variant] || row.variant;
    const status={passed:'通过',failed:'失败',not_run:'未运行',error:'执行错误',timeout:'超时'}[row.status] || row.status;
    const count=row.assertions.find(item=>item.field==='object_count');
    const detail=count && typeof count.actual==='number' ? '，实际保存 '+count.actual+' 个对象' : '';
    add(list,'li',variant+'：'+status+detail);
  }
  for (const item of reveal.unknowns) add(root,'p',item).className='muted';
  el('third').hidden=false;
  el('reveal').disabled=true;
  el('third-title').focus();
});
</script></body></html>'''
