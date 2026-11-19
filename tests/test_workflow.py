import tempfile
import unittest
from pathlib import Path
import workflow
import verify

class WorkflowV2Tests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name)
    def tearDown(self):self.tmp.cleanup()
    def test_secret_exclusion(self):
        (self.root/'config.py').write_text('api_key = "'+'x'*32+'"')
        (self.root/'.env').write_text('SECRET=value')
        s=workflow.scan(self.root);self.assertEqual(s['files'],{})
        self.assertEqual({x['reason'] for x in s['skipped']},{'possible_secret','sensitive_filename'})
    def test_scan_budget(self):
        (self.root/'a.py').write_text('a');(self.root/'b.py').write_text('b')
        s=workflow.scan(self.root,max_files=1);self.assertEqual(len(s['files']),1);self.assertEqual(s['skipped'][0]['reason'],'scan_budget')
    def test_scan_size_budget(self):
        (self.root/'a.py').write_text('12345')
        self.assertEqual(workflow.scan(self.root,max_bytes=4)['files'],{})
    def test_binary_exclusion(self):
        (self.root/'binary.py').write_bytes(b'a\0b')
        self.assertEqual(workflow.scan(self.root)['skipped'][0]['reason'],'binary_content')
    def test_empty_assertions_not_run(self):self.assertEqual(workflow.assertion_status([]),'not_run')
    def test_missing_field_error(self):self.assertEqual(workflow.assertion_status(workflow.assert_observation({},[{'field':'count','op':'equals','value':1}])),'error')
    def test_boolean_not_integer(self):self.assertEqual(workflow.assert_observation({'count':True},[{'field':'count','op':'equals','value':1}])[0]['status'],'failed')
    def test_unknown_operator_reject(self):
        with self.assertRaises(ValueError):workflow.assert_observation({},[{'field':'x','op':'eval','value':'shell'}])
    def test_failed_check_contradicts(self):self.assertEqual(workflow.derive_state('R1',[],[{'requirement_ids':['R1'],'status':'failed'}],[])['state'],'contradicted')
    def test_timeout_blocks(self):self.assertEqual(workflow.derive_state('R1',[],[{'requirement_ids':['R1'],'status':'timeout'}],[])['state'],'blocked')
    def test_pass_not_full_acceptance(self):self.assertEqual(workflow.derive_state('R1',[],[{'requirement_ids':['R1'],'status':'passed'}],[])['state'],'checks_passed')
    def test_review_wrong_version(self):
        with self.assertRaises(ValueError): workflow.import_reviews([{'input_snapshot':'old'}],'new',{'R1'})
    def test_contest_requires_evidence(self):
        with self.assertRaises(ValueError): workflow.import_reviews([{'input_snapshot':'s','id':'1','requirement_id':'R1','disposition':'contest'}],'s',{'R1'})
    def test_blocker_not_declined(self):
        with self.assertRaises(ValueError): workflow.import_reviews([{'input_snapshot':'s','id':'1','requirement_id':'R1','severity':'blocker','disposition':'decline'}],'s',{'R1'})
    def test_graph_ready_blocked(self):
        g=workflow.task_graph({'read':[],'test':['read'],'review':['test']},{'read'})
        self.assertEqual(g['test']['state'],'ready');self.assertEqual(g['review']['blocked_by'],['test'])
    def test_graph_cycle(self):
        with self.assertRaises(ValueError): workflow.task_graph({'a':['b'],'b':['a']},set())
    def test_graph_unknown_dep(self):
        with self.assertRaises(ValueError): workflow.task_graph({'a':['b']},set())
    def test_agent_packet_has_snapshot(self):
        (self.root/'plan.md').write_text('- R1: sample\n')
        r=verify.investigate(self.root,self.root/'plan.md')
        self.assertEqual(workflow.packet(r)['input_snapshot'],r['snapshot']['id'])
    def test_missing_requirements_rejected(self):
        (self.root/'plan.md').write_text('Unstructured prose')
        with self.assertRaises(ValueError):verify.investigate(self.root,self.root/'plan.md')
    def test_duplicate_requirements_rejected(self):
        (self.root/'plan.md').write_text('- R1: a\n- R1: b\n')
        with self.assertRaises(ValueError):verify.investigate(self.root,self.root/'plan.md')
    def test_proposed_fix_remains_blocked(self):
        self.assertEqual(workflow.derive_state('R1',[],[{'requirement_ids':['R1'],'status':'passed'}],[{'requirement_id':'R1','disposition':'propose_fix'}])['state'],'blocked')
    def test_plan_secret_rejected(self):
        (self.root/'plan.md').write_text('password="abcdefghijk"')
        with self.assertRaises(ValueError):verify.snapshot(self.root,self.root/'plan.md')
    def test_demo_comparison(self):
        r=verify.demo(self.root/'out')
        self.assertEqual(r['comparison']['baseline']['states']['R1']['state'],'contradicted')
        self.assertEqual(r['comparison']['fixed']['states']['R1']['state'],'checks_passed')
        self.assertEqual(r['comparison']['fixed']['states']['R3']['state'],'needs_evidence')
        self.assertEqual(r['gate']['state'],'not_accepted')

if __name__=='__main__':unittest.main()
