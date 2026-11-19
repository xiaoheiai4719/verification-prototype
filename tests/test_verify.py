import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import verify

class WorkflowTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.repo = self.root/'repo'; self.repo.mkdir()
        self.plan = self.root/'plan.md'; self.plan.write_text('- R1: no duplicate\n')
        (self.repo/'a.py').write_text('first\nsecond\n')
    def tearDown(self): self.tmp.cleanup()
    def report(self, items=None): return verify.investigate(self.repo,self.plan,items)
    def proposal(self): return {'requirement_id':'R1','claim':'candidate','references':[{'file':'a.py','start':1,'end':2}]}
    def test_requirements_not_verified(self):
        r=self.report(); self.assertEqual(r['requirements'][0]['status'],'unverified');self.assertEqual(r['runs'],[])
    def test_source_quote_is_actual(self):
        r=self.report([self.proposal()]);self.assertEqual(r['claims'][0]['references'][0]['quote'],'first\nsecond')
    def test_fake_status_rejected(self):
        p=self.proposal();p['status']='verified'
        with self.assertRaises(ValueError): self.report([p])
    def test_unknown_requirement_rejected(self):
        p=self.proposal();p['requirement_id']='R100'
        with self.assertRaises(ValueError): self.report([p])
    def test_missing_file_rejected(self):
        p=self.proposal();p['references'][0]['file']='missing.py'
        with self.assertRaises(ValueError): self.report([p])
    def test_path_escape_rejected(self):
        p=self.proposal();p['references'][0]['file']='../plan.md'
        with self.assertRaises(ValueError): self.report([p])
    def test_invalid_line_rejected(self):
        p=self.proposal();p['references'][0]['end']=99
        with self.assertRaises(ValueError): self.report([p])
    def test_source_change_marks_stale(self):
        r=self.report();self.assertFalse(verify.stale(r,self.repo,self.plan))
        (self.repo/'a.py').write_text('changed');self.assertTrue(verify.stale(r,self.repo,self.plan))
    def test_plan_change_marks_stale(self):
        r=self.report();self.plan.write_text('- R1: changed');self.assertTrue(verify.stale(r,self.repo,self.plan))
    def test_symlink_not_read(self):
        (self.repo/'outside.py').symlink_to(self.plan)
        self.assertNotIn('outside.py',self.report()['snapshot']['files'])
    def test_html_escaping(self):
        p=self.proposal();p['claim']='<script>alert(1)</script>'
        page=verify.render(self.report([p]));self.assertNotIn('<script>',page);self.assertIn('&lt;script&gt;',page)
    def test_no_arbitrary_execution(self):
        with self.assertRaises(ValueError): verify.run_demo_probe('shell','normal')
    def test_nonzero_probe_is_not_pass(self):
        r=verify.run_demo_probe('baseline','lost_response');self.assertEqual(r['status'],'failed');self.assertEqual(json.loads(r['stdout'])['object_count'],2)
    def test_fixed_probe_pass(self):
        self.assertEqual(verify.run_demo_probe('fixed','lost_response')['status'],'passed')
    def test_probe_timeout(self):
        with patch('verify.subprocess.run',side_effect=verify.subprocess.TimeoutExpired('demo',5)):
            self.assertEqual(verify.run_demo_probe('fixed','normal')['status'],'timeout')
    def test_runner_error(self):
        with patch('verify.subprocess.run',return_value=verify.subprocess.CompletedProcess([],2,'oops','error')):
            self.assertEqual(verify.run_demo_probe('fixed','normal')['status'],'error')
    def test_timeout_keeps_provenance_and_blocks_requirement(self):
        with patch('verify.subprocess.run',side_effect=verify.subprocess.TimeoutExpired('demo',5)):
            run=verify.run_demo_probe('fixed','lost_response')
        self.assertEqual(run.get('requirement_ids'),['R1'])
        self.assertTrue(run.get('runner_sha256'))
        self.assertEqual(verify.workflow.derive_state('R1',[],[run],[])['state'],'blocked')
    def test_empty_observation_is_error_not_counterexample(self):
        with patch('verify.subprocess.run',return_value=verify.subprocess.CompletedProcess([],0,'{}','')):
            run=verify.run_demo_probe('fixed','lost_response')
        self.assertEqual(run['status'],'error')
        self.assertEqual(verify.workflow.derive_state('R1',[],[run],[])['state'],'blocked')
    def test_changed_runner_marks_stale(self):
        r=self.report()
        r['runs']=[verify.run_demo_probe('fixed','normal')]
        self.assertFalse(verify.stale(r,self.repo,self.plan))
        r['runs'][0]['runner_sha256']='old-runner'
        self.assertTrue(verify.stale(r,self.repo,self.plan))
    def test_missing_runner_provenance_marks_stale(self):
        r=self.report();r['runs']=[{'status':'passed'}]
        self.assertTrue(verify.stale(r,self.repo,self.plan))
    def test_runner_file_changes_invalidate_results(self):
        r=self.report(); r['runs']=[verify.run_demo_probe('fixed','normal')]
        runner_dir=self.root/'runner';runner_dir.mkdir()
        names=('verify.py','workflow.py','demo_probe.py')
        originals={name:(verify.BASE/name).read_bytes() for name in names}
        for name,data in originals.items(): (runner_dir/name).write_bytes(data)
        with patch('verify.BASE',runner_dir):
            self.assertFalse(verify.stale(r,self.repo,self.plan))
            for name in names:
                with self.subTest(file=name):
                    (runner_dir/name).write_bytes(originals[name]+b'\n# changed\n')
                    self.assertTrue(verify.stale(r,self.repo,self.plan))
                    (runner_dir/name).write_bytes(originals[name])
    def test_non_object_json_is_error(self):
        for output in ('null','[]','42','"text"'):
            with self.subTest(output=output), patch('verify.subprocess.run',return_value=verify.subprocess.CompletedProcess([],0,output,'')):
                self.assertEqual(verify.run_demo_probe('fixed','normal')['status'],'error')
    def test_full_demo_artifact(self):
        report=verify.demo(self.root/'out')
        self.assertEqual([x['status'] for x in report['runs']],['passed','failed','passed','passed'])
        self.assertTrue((self.root/'out/report.html').is_file())
        self.assertEqual(len({x['input_snapshot'] for x in report['runs']}),1)

if __name__=='__main__': unittest.main()
