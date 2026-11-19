import copy
import contextlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import rederive
import verify


class DecisionRehearsalTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.repo = self.root/'repo'; self.repo.mkdir()
        (self.repo/'source.py').write_text('def operation():\n    return "SOURCE_SECRET"\n')
        self.plan = self.root/'plan.md'; self.plan.write_text('- R1: One operation\n')
        self.report = verify.investigate(self.repo, self.plan)
        self.spec = {'id':'card-1','requirement_id':'R1','problem':'Which uncertainty matters?',
            'hints':['HINT_ONE','HINT_TWO'],'constraints':['CONSTRAINT_ONE','CONSTRAINT_TWO'],
            'reveal':{'explanation':'ANSWER_SECRET','references':[{'file':'source.py','start':1,'end':2}],
                      'unknowns':['UNKNOWN_SECRET'],'tradeoffs':['TRADEOFF_SECRET'],
                      'acceptance_checks':['CHECK_SECRET']}}
        self.card = rederive.create_card(self.report, self.spec)
        self.session = rederive.start_session(self.report, self.card)

    def view(self, session=None):
        return rederive.public_view(self.report,self.card,session or self.session)

    def test_initial_view_contains_no_solution_source_hint_or_test_status(self):
        view=self.view(); text=json.dumps(view)
        self.assertEqual(view['phase'],'question')
        for secret in ('SOURCE_SECRET','ANSWER_SECRET','HINT_ONE','HINT_TWO','CONSTRAINT_ONE',
                       'UNKNOWN_SECRET','TRADEOFF_SECRET','CHECK_SECRET','test_status','references'):
            self.assertNotIn(secret,text)

    def test_cannot_skip_first_answer(self):
        for action in (rederive.hint,rederive.reveal):
            with self.assertRaises(ValueError): action(self.report,self.card,self.session)

    def test_blank_answer_rejected(self):
        for text in ('','   ',None,True,'x'*20001):
            with self.assertRaises(ValueError): rederive.answer(self.session,text)

    def test_first_answer_immutable(self):
        session=rederive.answer(self.session,'My hypothesis')
        self.assertEqual(self.session['first_answer'],None)
        self.assertEqual(self.view(session)['first_answer'],'My hypothesis')
        with self.assertRaises(ValueError): rederive.answer(session,'overwrite')

    def test_progressive_hints_and_constraints(self):
        session=rederive.answer(self.session,'My hypothesis')
        session=rederive.hint(self.report,self.card,session)
        view=self.view(session)
        self.assertEqual(view['hints'],['HINT_ONE'])
        self.assertEqual(view['constraints'],['CONSTRAINT_ONE'])
        self.assertNotIn('HINT_TWO',json.dumps(view))
        self.assertNotIn('ANSWER_SECRET',json.dumps(view))
        session=rederive.hint(self.report,self.card,session)
        self.assertEqual(self.view(session)['hints'],['HINT_ONE','HINT_TWO'])
        with self.assertRaises(ValueError): rederive.hint(self.report,self.card,session)

    def test_reveal_source_backed_not_graded_or_accepted(self):
        session=rederive.reveal(self.report,self.card,rederive.answer(self.session,'My hypothesis'))
        reveal=self.view(session)['reveal']
        self.assertEqual(reveal['references'][0]['quote'],'def operation():\n    return "SOURCE_SECRET"')
        self.assertEqual(reveal['references'][0]['sha256'],self.report['snapshot']['files']['source.py']['sha256'])
        self.assertEqual(reveal['business_acceptance'],'not_accepted')
        self.assertEqual(reveal['test_status']['runs'],[])
        self.assertEqual(reveal['test_status']['state'],'needs_evidence')
        with self.assertRaises(ValueError): rederive.hint(self.report,self.card,session)

    def test_bad_source_rejected(self):
        for ref in ({'file':'../x','start':1,'end':2},
                    {'file':'source.py','start':True,'end':2},
                    {'file':'source.py','start':1,'end':99},
                    {'file':'source.py','start':1,'end':2,'quote':'forged'}):
            spec=copy.deepcopy(self.spec);spec['reveal']['references']=[ref]
            with self.assertRaises(ValueError): rederive.create_card(self.report,spec)

    def test_source_required(self):
        spec=copy.deepcopy(self.spec);spec['reveal']['references']=[]
        with self.assertRaises(ValueError): rederive.create_card(self.report,spec)

    def test_authored_status_rejected(self):
        for key in ('runs','status','business_acceptance','test_status'):
            spec=copy.deepcopy(self.spec);spec[key]='passed'
            with self.assertRaises(ValueError): rederive.create_card(self.report,spec)
            spec=copy.deepcopy(self.spec);spec['reveal'][key]='passed'
            with self.assertRaises(ValueError): rederive.create_card(self.report,spec)

    def test_duplicate_cards_rejected(self):
        with self.assertRaises(ValueError): rederive.import_cards(self.report,[self.spec,self.spec])

    def test_unknown_requirement_rejected(self):
        self.spec['requirement_id']='R999'
        with self.assertRaises(ValueError): rederive.create_card(self.report,self.spec)

    def test_invalid_hints_or_constraints_rejected(self):
        for key,value in (('hints','not list'),('hints',[{}]),('constraints',['1','2','3'])):
            spec=copy.deepcopy(self.spec);spec[key]=value
            with self.assertRaises(ValueError): rederive.create_card(self.report,spec)

    def test_card_and_session_binding(self):
        changed=copy.deepcopy(self.card);changed['problem']='changed'
        with self.assertRaises(ValueError): rederive.start_session(self.report,changed)
        self.report['snapshot']['id']='changed'
        with self.assertRaises(ValueError): self.view()

    def test_report_runs_change_invalidates_session(self):
        self.report['runs'].append({'status':'passed'})
        with self.assertRaises(ValueError): self.view()

    def test_review_change_invalidates_session(self):
        self.report['reviews']=[{'message':'new'}]
        with self.assertRaises(ValueError): self.view()

    def test_session_card_mismatch_rejected(self):
        self.session['card_id']='other'
        with self.assertRaises(ValueError): self.view()

    def test_malformed_progress_rejected(self):
        for count in (-1,3,True,'1'):
            session=copy.deepcopy(self.session);session['hint_count']=count
            with self.assertRaises(ValueError): self.view(session)

    def test_forged_progress_without_answer_rejected(self):
        for key,value in (('hint_count',1),('revealed',True)):
            session=copy.deepcopy(self.session);session[key]=value
            with self.assertRaises(ValueError): self.view(session)

    def test_test_status_keeps_variants_and_errors(self):
        self.report['runs']=[
            {'variant':'baseline','status':'failed','requirement_ids':['R1'],'input_snapshot':self.report['snapshot']['id']},
            {'variant':'fixed','status':'passed','requirement_ids':['R1'],'input_snapshot':self.report['snapshot']['id']}]
        status=rederive.test_status(self.report,self.card)
        self.assertEqual(status['by_variant']['baseline']['state'],'contradicted')
        self.assertEqual(status['by_variant']['fixed']['state'],'checks_passed')
        self.report['runs'][1]['input_snapshot']='old'
        self.assertEqual(rederive.test_status(self.report,self.card)['by_variant']['fixed']['state'],'blocked')
        self.assertEqual(self.report['runs'][1]['status'],'passed') # output conversion doesn't mutate audit input

    def test_error_and_timeout_are_not_counterexamples(self):
        for state in ('error','timeout','not_run'):
            self.report['runs']=[{'status':state,'requirement_ids':['R1'],
                'input_snapshot':self.report['snapshot']['id']}]
            self.assertEqual(rederive.test_status(self.report,self.card)['state'],'blocked')

    def cli(self,*args):
        out,err=io.StringIO(),io.StringIO()
        with patch('sys.argv',['verify.py',*args]),contextlib.redirect_stdout(out),contextlib.redirect_stderr(err):
            code=verify.main()
        return code,out.getvalue(),err.getvalue()

    def cli_setup(self):
        self.report['decision_cards']=[self.card]
        self.report_path=self.root/'report.json'
        self.report_path.write_text(json.dumps(self.report))
        self.session_path=self.root/'session.json'
        return ['--report',str(self.report_path),'--card','card-1','--session',str(self.session_path),
                '--repo',str(self.repo),'--plan',str(self.plan)]

    def test_cli_full_flow_and_repeat_start(self):
        args=self.cli_setup()
        self.assertEqual(self.cli('learn','start',*args)[0],0)
        self.assertEqual(self.cli('learn','start',*args)[0],2)
        self.assertEqual(self.cli('learn','hint',*args)[0],2)
        self.assertEqual(self.cli('learn','answer',*args,'--text','Initial reasoning')[0],0)
        self.assertEqual(self.cli('learn','hint',*args)[0],0)
        code,out,_=self.cli('learn','view',*args)
        self.assertEqual(code,0);self.assertNotIn('ANSWER_SECRET',out)
        code,out,_=self.cli('learn','reveal',*args)
        self.assertEqual(code,0);self.assertIn('SOURCE_SECRET',out)

    def test_cli_rejects_stale_repo_without_overwriting_session(self):
        args=self.cli_setup();self.cli('learn','start',*args)
        previous=self.session_path.read_bytes()
        (self.repo/'source.py').write_text('changed')
        self.assertEqual(self.cli('learn','answer',*args,'--text','new')[0],2)
        self.assertEqual(self.session_path.read_bytes(),previous)

    def test_cli_rejects_stale_runner(self):
        args=self.cli_setup()
        self.report['runs']=[{'runner_sha256':'old','status':'passed'}]
        self.report_path.write_text(json.dumps(self.report))
        self.assertEqual(self.cli('learn','start',*args)[0],2)

    def test_inspect_cards_and_safe_export(self):
        path=self.root/'cards.json';path.write_text(json.dumps([self.spec]))
        out=self.root/'out'
        code,_,_=self.cli('inspect','--repo',str(self.repo),'--plan',str(self.plan),
                         '--cards',str(path),'--out',str(out))
        self.assertEqual(code,0)
        public=(out/'decision-cards.json').read_text()
        self.assertNotIn('ANSWER_SECRET',public)
        self.assertNotIn('SOURCE_SECRET',public)
        report=json.loads((out/'report.json').read_text())
        self.assertEqual(len(report['decision_cards']),1)
        self.assertEqual(report['gate']['state'],'not_accepted')
        self.assertEqual(report['runs'],[])


if __name__=='__main__':
    unittest.main()
