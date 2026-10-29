"""Offline negative paths. Fake model responses here are never live Meta evidence."""
import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from wheel import experiment
from wheel.meta_agent import MetaAgent
from wheel.preflight import MockRefundTool, TriggerNotReached
from wheel.plan_guard import PlanGuard, IntegrityError, sha
from test_meta_agent import FakeClient, message, ARGS

class PreflightTests(unittest.TestCase):
    def test_mock_has_no_network_and_never_claims_committed(self):
        tool=MockRefundTool()
        with patch('socket.socket', side_effect=AssertionError('No network allowed')):
            receipt=tool.issue_refund(**ARGS)
        self.assertEqual(receipt['status'],'validated_without_execution')
        self.assertEqual(receipt['mode'],'mock_only')
        self.assertEqual(tool.calls,[ARGS])
        with self.assertRaises(ValueError): tool.issue_refund(**ARGS)

    def test_both_mocks_run_before_seed_exposure_and_mock_result_is_not_replayed(self):
        agent=MetaAgent(FakeClient())
        responses=[message(), message({**ARGS,'amount_minor_units':7500})]
        with patch.object(agent,'generate',side_effect=responses), patch.object(
                MockRefundTool,'issue_refund',autospec=True,
                side_effect=lambda tool, **args: {'mode':'mock_only','status':'validated_without_execution'}) as mock:
            frozen=agent.prepare()
        self.assertEqual(mock.call_count,2)
        self.assertEqual(len(agent.preflights),2)
        for case in ['M1','M2']:
            seed=frozen[case]['payload']
            self.assertNotIn('mock_only',json.dumps(seed))
            self.assertNotIn('idempotency_key',seed['arguments'])
            self.assertEqual(seed['messages'][-1]['role'],'assistant')
        with self.assertRaises(RuntimeError): agent.prepare()

    def test_second_failure_exposes_no_partial_seed(self):
        agent=MetaAgent(FakeClient())
        with patch.object(agent,'generate',side_effect=[message(),{'role':'assistant','content':'No tool'}]):
            with self.assertRaises(TriggerNotReached): agent.prepare()
        self.assertEqual(agent.frozen,{})
        self.assertFalse(agent.prepared)
        self.assertEqual(agent.preflights[-1]['status'],'trigger_not_reached')

    def test_failed_trigger_cannot_build_or_start_worlds(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            for name in [experiment.DOMAIN,experiment.CLIENT]:
                dest=root/name;dest.parent.mkdir(parents=True,exist_ok=True)
                dest.write_bytes((experiment.ROOT/name).read_bytes())
            agent=MetaAgent(FakeClient({'role':'assistant','content':'No tool'}))
            with patch.object(experiment,'ROOT',root), patch.object(experiment.subprocess,'run') as build, patch.object(experiment,'start') as start:
                with self.assertRaises(TriggerNotReached): experiment.run(agent)
            build.assert_not_called();start.assert_not_called()
            self.assertFalse((root/'evidence-g4/frozen-plan.json').exists())
            self.assertFalse((root/'evidence-g4/summary.json').exists())
            records=json.loads((root/'evidence-g4/preflight.json').read_text())
            self.assertEqual(records[0]['status'],'trigger_not_reached')

class FrozenGateTests(unittest.TestCase):
    def test_runner_blocks_world_start_if_build_changes_oracle(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            for name in [experiment.DOMAIN,experiment.CLIENT,'wheel/verifier.py','wheel/proxy.py',
                         experiment.JAVA+'/pom.xml','services/support-agent-python/pyproject.toml']:
                dest=root/name;dest.parent.mkdir(parents=True,exist_ok=True)
                dest.write_bytes((experiment.ROOT/name).read_bytes())
            calls=[]
            def fake_build(*args, **kwargs):
                calls.append(1)
                jar=root/experiment.JAVA/'target/refund-api-java-0.1.0-SNAPSHOT.jar'
                jar.parent.mkdir(parents=True,exist_ok=True);jar.write_bytes(b'offline fake jar')
                if len(calls)==3: (root/'wheel/verifier.py').write_text('tampered')
            with patch.object(experiment,'ROOT',root), patch.object(experiment.subprocess,'run',side_effect=fake_build), patch.object(experiment,'start') as start:
                with self.assertRaises(IntegrityError): experiment.run()
            start.assert_not_called()
            self.assertFalse((root/'evidence/summary.json').exists())

    def test_stale_success_directory_is_rejected_before_preflight(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);out=root/'evidence-g4';out.mkdir()
            (out/'summary.json').write_text('{"status":"old run"}')
            agent=Mock()
            with patch.object(experiment,'ROOT',root), self.assertRaisesRegex(RuntimeError,'empty'):
                experiment.run(agent)
            agent.prepare.assert_not_called()

    def test_each_bound_artifact_tamper_blocks_execution_and_publication(self):
        for name in ['plan','source','oracle','fixture','wrapper','jar','preflight']:
            with self.subTest(name=name), tempfile.TemporaryDirectory() as directory:
                root=Path(directory);plan=root/'plan';plan.write_bytes(b'plan')
                paths=[]
                for other in ['source','oracle','fixture','wrapper','jar','preflight']:
                    p=root/other;p.write_bytes(other.encode());paths.append(p)
                guard=PlanGuard(plan,b'plan',paths)
                guard.verify('accepted')
                (root/name).write_bytes(b'tampered')
                operation=Mock()
                with self.assertRaises(IntegrityError): guard.call('before_world',operation)
                operation.assert_not_called()
                with self.assertRaises(IntegrityError): guard.publish(root/'summary',{'status':'verified'})
                self.assertFalse((root/'summary').exists())

    def test_rewriting_hash_sidecar_does_not_reauthorize_plan(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);plan=root/'plan';plan.write_bytes(b'original')
            guard=PlanGuard(plan,b'original',[])
            plan.write_bytes(b'changed');(root/'plan.sha256').write_text(sha(b'changed'))
            with self.assertRaises(IntegrityError): guard.verify('before_world')
            with self.assertRaises(IntegrityError): guard.bind(plan,b'changed')

    def test_missing_file_and_symlink_are_rejected(self):
        for mode in ['missing','symlink']:
            with tempfile.TemporaryDirectory() as directory:
                root=Path(directory);plan=root/'plan';plan.write_bytes(b'original')
                guard=PlanGuard(plan,b'original',[]);plan.unlink()
                if mode=='symlink':
                    target=root/'target';target.write_bytes(b'original');plan.symlink_to(target)
                with self.assertRaises(IntegrityError): guard.verify('before_world')

    def test_gate_rechecks_after_successful_world_before_summary(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);plan=root/'plan';plan.write_bytes(b'original')
            guard=PlanGuard(plan,b'original',[])
            called=Mock(return_value='world result')
            self.assertEqual(guard.call('before_world',called),'world result')
            plan.write_bytes(b'late tampering')
            with self.assertRaises(IntegrityError): guard.publish(root/'summary',{'status':'verified'})
            self.assertFalse((root/'summary').exists())

if __name__=='__main__': unittest.main()
