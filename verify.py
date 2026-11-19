#!/usr/bin/env python3
"""Evidence-first prototype. No model API and no arbitrary repository execution."""
import argparse
import hashlib
import html
import json
import re
import subprocess
import sys
import time
from pathlib import Path
import workflow
import rederive

BASE = Path(__file__).resolve().parent
IGNORE = {'.git', '.venv', 'node_modules', '__pycache__', '.aws', '.codex'}
EXTENSIONS = {'.py', '.md', '.json', '.yaml', '.yml', '.ts', '.js', '.java', '.toml'}

def digest(data):
    return hashlib.sha256(data).hexdigest()

def inventory(root):
    return workflow.scan(root)['files']

def snapshot(repo, plan):
    scanned = workflow.scan(repo)
    files = scanned["files"]
    if Path(plan).stat().st_size > 200_000: raise ValueError('Plan exceeds 200KB limit')
    plan_bytes = Path(plan).read_bytes()
    if any(re.search(pattern,plan_bytes.decode('utf-8')) for pattern in workflow.SECRET_PATTERNS):
        raise ValueError('Potential secret in plan; remove before importing')
    signature = {'files': {name: data['sha256'] for name, data in files.items()}, 'skipped': scanned['skipped']}
    return {'id': digest(json.dumps(signature, sort_keys=True).encode() + plan_bytes),
            'files': files, 'skipped': scanned['skipped'], 'budget': scanned['budget'], 'plan_sha256': digest(plan_bytes),
            'plan': plan_bytes.decode('utf-8'),
            'scope': 'Bounded UTF-8 scan; exclusions enumerated. Heuristic secret screening is incomplete.'}

def reference(snap, file, start, end):
    if file not in snap['files']:
        raise ValueError('Unknown source file')
    lines = snap['files'][file]['text'].splitlines()
    if isinstance(start, bool) or isinstance(end, bool) or not isinstance(start, int) or not isinstance(end, int) or not 1 <= start <= end <= len(lines):
        raise ValueError('Invalid source range')
    return {'file': file, 'start': start, 'end': end,
            'sha256': snap['files'][file]['sha256'],
            'quote': '\n'.join(lines[start-1:end])}

def investigate(repo, plan, proposals=None):
    snap = snapshot(repo, plan)
    requirements = [{'id': m[0], 'text': m[1], 'status': 'unverified'}
                    for m in re.findall(r'^- (R\d+): (.+)$', snap['plan'], re.M)]
    if not requirements: raise ValueError('No Rn requirements found; extract requirements before inspection')
    if len({r['id'] for r in requirements})!=len(requirements): raise ValueError('Duplicate requirement ID')
    report = {'schema': 2, 'mode': 'offline evidence workflow; no live model',
              'created_at': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
              'snapshot': snap, 'requirements': requirements, 'claims': [], 'runs': [],
              'limitations': ['No model was called. Requirements use explicit Rn markers; free prose needs human/Agent review.',
                              'Source references prove location, not the truth or completeness of the claim.',
                              'No arbitrary repository tests are executed. Demo tests use only bundled fictional code.',
                              'Hashes provide change detection, not authenticity or tamper-proof storage.']}
    for item in proposals or []:
        if item.get('status') or item.get('runs'):
            raise ValueError('Proposals cannot set verification status or execution results')
        if item['requirement_id'] not in {r['id'] for r in requirements}:
            raise ValueError('Unknown requirement')
        refs = [reference(snap, r['file'], r['start'], r['end']) for r in item.get('references', [])]
        report['claims'].append({'requirement_id': item['requirement_id'], 'claim': item['claim'],
                                'origin': 'human/Agent supplied proposal, not independent discovery',
                                'status': 'source_located' if refs else 'unverified',
                                'references': refs, 'next_step': item.get('next_step', '')})
    return report

def runner_hash():
    # Bind probe AND execution/assertion semantics, not only the fixture launcher.
    files = {name: digest((BASE/name).read_bytes())
             for name in ('demo_probe.py', 'verify.py', 'workflow.py')}
    return digest(json.dumps(files, sort_keys=True).encode())

def run_demo_probe(variant, scenario):
    if variant not in {'baseline', 'fixed'} or scenario not in {'normal', 'lost_response'}:
        raise ValueError('Unknown bundled probe')
    command = [sys.executable, '-I', str(BASE / 'demo_probe.py'), variant, scenario]
    # -I omits the script directory; bootstrap only our known source path.
    command = [sys.executable, '-I', '-c',
               'import sys,runpy;sys.path.insert(0,sys.argv[1]);sys.argv=sys.argv[2:];runpy.run_path(sys.argv[0],run_name="__main__")',
               str(BASE), str(BASE/'demo_probe.py'), variant, scenario]
    provenance = {'variant': variant, 'scenario': scenario,
                  'requirement_ids': ['R1'] if scenario == 'lost_response' else ['R2'],
                  'runner_sha256': runner_hash(),
                  'scope': 'Bundled FakeStorage only; NOT a real provider validation'}
    started = time.monotonic()
    try:
        p = subprocess.run(command, capture_output=True, text=True, timeout=5, cwd=BASE)
        output = p.stdout
        try:
            observed = json.loads(output)
        except ValueError:
            observed = None
        assertions = workflow.assert_observation(observed if isinstance(observed, dict) else {}, [{'field':'object_count','op':'equals','value':1},{'field':'returned_id','op':'equals','value':1}])
        status = workflow.assertion_status(assertions)
        if not isinstance(observed, dict) or p.returncode not in {0, 1}:
            status = 'error'
        elif p.returncode != 0 and status == 'passed':
            # Exit status disagrees with assertions: execution failure, not business proof.
            status = 'error'
        return {**provenance, 'status': status, 'exit_code': p.returncode,
                'assertions': assertions, 'stdout': output, 'stderr': p.stderr,
                'seconds': round(time.monotonic()-started, 4)}
    except subprocess.TimeoutExpired:
        return {**provenance, 'status': 'timeout', 'exit_code': None, 'assertions': [],
                'stdout': '', 'stderr': 'Exceeded 5 seconds',
                'seconds': round(time.monotonic()-started, 4)}

def stale(report, repo, plan):
    if report['snapshot']['id'] != snapshot(repo, plan)['id']:
        return True
    current_runner = runner_hash()
    return any(run.get('runner_sha256') != current_runner for run in report.get('runs', []))

def render(report):
    workflow.enrich(report)
    e = html.escape
    cards = []
    for r in report['requirements']:
        state=report['workflow'][r['id']]
        cards.append(f'<article><span class="pill">{e(state["state"])} / 未验收</span><h3>{e(r["id"])} · {e(r["text"])}</h3></article>')
    claims = []
    for c in report['claims']:
        refs = ''.join(f'<details><summary>{e(r["file"])}:{r["start"]}–{r["end"]} · 查看原始证据</summary><pre>{e(r["quote"])}</pre></details>' for r in c['references'])
        claims.append(f'<article><span class="pill">来源已定位，不等于结论已证明</span><h3>{e(c["claim"])}</h3>{refs}<p>下一步：{e(c["next_step"])}</p></article>')
    runs = ''.join(f'<article><span class="pill {r["status"]}">{e(r["status"])}</span><h3>{e(r["variant"])} / {e(r["scenario"])}</h3><p>{e(r.get("scope", ""))}</p><details><summary>查看实际执行输出</summary><pre>{e(r["stdout"]+r["stderr"])}</pre></details></article>' for r in report['runs'])
    skipped=''.join('<li>'+e(x['path'])+' · '+e(x['reason'])+'</li>' for x in report['snapshot'].get('skipped',[]))
    task_block='<h2>07 · 下一步与阻塞</h2><article>'+''.join('<p>'+e(k)+' · '+e(v['state'])+('，等待 '+e(', '.join(v['blocked_by'])) if v['blocked_by'] else '')+'</p>' for k,v in report['tasks'].items())+'</article>'
    scan_block='<h2>05 · 扫描边界</h2><article><p>排除项与预算可见；不是完整仓库审计，也不保证无秘密。</p><ul>'+skipped+'</ul></article>'
    comparison=''.join('<article><h3>'+e(v)+'</h3>'+''.join('<p>'+e(k)+': '+e(s['state'])+'</p>' for k,s in c['states'].items())+'</article>' for v,c in report.get('comparison',{}).items())
    rehearsal = ''
    if report.get('decision_cards'):
        rows = ''.join('<li><code>'+e(c['id'])+'</code> · '+e(c['requirement_id'])+'</li>'
                       for c in report['decision_cards'])
        link = '<a href="learn.html">开始样例推演</a>（建议先做题，再读本报告）。' if report['runs'] else '用 learn CLI 逐步推演；本报告可能包含答案。'
        rehearsal = '<article><h2>设计推演</h2><p>'+link+'</p><ul>'+rows+'</ul></article>'
    review_block='<h2>06 · 审阅意见</h2><article>'+(''.join('<p>'+e(x['disposition'])+' · '+e(x['message'])+'</p>' for x in report.get('reviews',[])) or '未导入独立审阅意见；不视为通过')+'</article>'
    return '''<!doctype html><html lang="zh"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>证据核验工作台</title><style>
body{margin:0;background:#f2f5fa;color:#182b42;font:16px/1.7 system-ui,sans-serif}main{max-width:960px;margin:auto;padding:32px 20px}header{background:#12273e;color:white;padding:28px;border-radius:18px}h1{margin:0;font-size:30px}h2{margin-top:32px}article{background:white;padding:20px;margin:12px 0;border-radius:12px;border:1px solid #dce4ee}h3{font-size:17px}pre{white-space:pre-wrap;overflow-wrap:anywhere;background:#f3f6fa;padding:14px;font:13px/1.6 monospace}.pill{font-size:12px;background:#fff0c7;color:#725000;padding:4px 10px;border-radius:20px}.passed{background:#d9f5e6;color:#12683c}.failed,.error{background:#ffe2e2;color:#9c2424}summary{cursor:pointer}small{overflow-wrap:anywhere}a{color:#1465c0}</style><main><header><p>可检查的结论 / 最小原型</p><h1>先看证据，再决定往前走</h1><p>这是离线工作流演示，不是已接入模型的自主审查产品。</p></header>''' + f'<p><small>输入快照 SHA256：{e(report["snapshot"]["id"])}</small></p>{rehearsal}<h2>01 · 方案要求</h2>'+''.join(cards)+'<h2>02 · 调查意见与源码</h2>'+''.join(claims)+'<h2>03 · 修改前后同一检查</h2>'+comparison+runs+'<h2>04 · 必须保留的未知</h2><article>所有要求均保持未验收，不因引用存在或几个测试通过自动宣称完成。需要确认业务预期、实际外部契约和未覆盖场景。演示中使用的 FakeStorage 不能证明真实供应商行为。</article><h2>范围与限制</h2><article>'+''.join('<p>'+e(x)+'</p>' for x in report['limitations'])+'</article>'+scan_block+review_block+task_block+'</main></html>'

def save(report, out):
    workflow.enrich(report)
    out = Path(out); out.mkdir(parents=True, exist_ok=True)
    (out/'report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2))
    (out/'report.html').write_text(render(report))
    (out/'agent-packet.json').write_text(json.dumps(workflow.packet(report),ensure_ascii=False,indent=2))
    (out/'decision-cards.json').write_text(json.dumps(
        [rederive.public_view(report, card, rederive.start_session(report, card))
         for card in report.get('decision_cards', [])], ensure_ascii=False, indent=2))


def demo(out):
    repo = BASE/'examples/upload'; plan = repo/'plan.md'
    snap = snapshot(repo, plan)
    lines = snap['files']['service.py']['text'].splitlines()
    start = next(i for i, s in enumerate(lines, 1) if s.startswith('def upload('))
    proposals = [{'requirement_id': 'R1', 'claim': '待验证：响应丢失后，未携带稳定身份的重试可能重复保存。',
                  'references': [{'file': 'service.py', 'start': start, 'end': start+7}],
                  'next_step': '模拟远端成功但响应丢失，检查对象数量；再对照幂等修正。'},
                 {'requirement_id': 'R3', 'claim': '真实供应商 24 小时幂等契约缺少材料。',
                  'references': [], 'next_step': '获得供应商版本化接口契约和真实测试环境；不要用假服务替代。'}]
    report = investigate(repo, plan, proposals)
    report['runs'] = [dict(run_demo_probe(v,s), input_snapshot=report['snapshot']['id'])
                      for v in ('baseline','fixed') for s in ('normal','lost_response')]
    report['comparison']={v:{'runs':[r for r in report['runs'] if r['variant']==v], 'states':{q['id']:workflow.derive_state(q['id'],report['claims'],[r for r in report['runs'] if r['variant']==v],[]) for q in report['requirements']}} for v in ('baseline','fixed')}
    # The bundled interactive lesson and CLI use the same snapshot-bound card.
    import demo_cards
    import rederive_web
    report['decision_cards'] = [rederive.create_card(report, spec) for spec in demo_cards.retry_specs()]
    save(report, out)
    (Path(out) / 'learn.html').write_text(rederive_web.render(report, report['decision_cards'][0]), encoding='utf-8')
    return report

def main():
    p=argparse.ArgumentParser(description=__doc__); sub=p.add_subparsers(dest='cmd',required=True)
    d=sub.add_parser('demo');d.add_argument('--out',default='outputs/demo')
    i=sub.add_parser('inspect');i.add_argument('--repo',required=True);i.add_argument('--plan',required=True);i.add_argument('--cards');i.add_argument('--proposals');i.add_argument('--reviews');i.add_argument('--out',default='outputs/inspection')
    c=sub.add_parser('check');c.add_argument('--report',required=True);c.add_argument('--repo',required=True);c.add_argument('--plan',required=True)
    l=sub.add_parser('learn', help='Offline first-answer decision rehearsal')
    l.add_argument('action', choices=('start','answer','hint','reveal','view'))
    for flag in ('report','card','session','repo','plan'):
        l.add_argument('--'+flag, required=True)
    l.add_argument('--text', help='Your first answer; never sent over the network')
    a=p.parse_args()
    if a.cmd=='learn':
        try:
            report=json.loads(Path(a.report).read_text())
            if stale(report,a.repo,a.plan):
                raise ValueError('STALE inputs or runner: regenerate report and start a new session')
            matches=[card for card in report.get('decision_cards',[]) if card['id']==a.card]
            if len(matches)!=1: raise ValueError('Unknown or duplicate decision card')
            card=matches[0]; path=Path(a.session)
            if a.action=='start':
                session=rederive.start_session(report,card)
                # Exclusive creation prevents accidental loss of a prior first answer.
                with path.open('x') as f: json.dump(session,f,ensure_ascii=False,indent=2)
            else:
                session=json.loads(path.read_text())
                rederive.public_view(report,card,session)
                if a.action=='answer': session=rederive.answer(session,a.text)
                elif a.action=='hint': session=rederive.hint(report,card,session)
                elif a.action=='reveal': session=rederive.reveal(report,card,session)
                rederive.public_view(report,card,session)
                if a.action!='view':
                    path.write_text(json.dumps(session,ensure_ascii=False,indent=2))
            print(json.dumps(rederive.public_view(report,card,session),ensure_ascii=False,indent=2))
            return 0
        except (ValueError, OSError, KeyError, TypeError) as exc:
            print('Rehearsal blocked: '+str(exc),file=sys.stderr)
            return 2
    if a.cmd=='demo':
        r=demo(a.out);print(json.dumps([{k:v for k,v in x.items() if k in ('variant','scenario','status')} for x in r['runs']],indent=2));return 0
    if a.cmd=='inspect':
        proposals=json.loads(Path(a.proposals).read_text()) if a.proposals else []
        report=investigate(a.repo,a.plan,proposals)
        if a.reviews:
            report['reviews']=workflow.import_reviews(json.loads(Path(a.reviews).read_text()),report['snapshot']['id'],{r['id'] for r in report['requirements']})
        if a.cards:
            report['decision_cards']=rederive.import_cards(report,json.loads(Path(a.cards).read_text()))
        save(report,a.out);print('Generated read-only evidence report; no tests executed.');return 0
    outdated=stale(json.loads(Path(a.report).read_text()),a.repo,a.plan)
    print('STALE: evidence must be rechecked' if outdated else 'MATCH: input and recorded runner hashes unchanged (not a correctness proof)');return 2 if outdated else 0

if __name__=='__main__':
    sys.exit(main())
