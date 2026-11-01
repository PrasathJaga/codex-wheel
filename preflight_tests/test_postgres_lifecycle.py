import copy
import unittest
from unittest.mock import patch

from preflight.petclinic_adapter import AdmissionError,digest
from preflight.postgres_lifecycle import admit_database,validate_seeds,PostgresWorld
from preflight_tests.test_execution_manifest import configured


class PostgresLifecycleTests(unittest.TestCase):
    def config(self):
        m,d=configured()
        p={'schema':'wheel-postgres-service-policy-v1','manifest_sha256':digest(m),
           'allowed_images':[m['projects'][0]['image']],'max_repetitions':2,'total_timeout_seconds':300}
        return m,d,p

    def test_policy_accepts_shared_java_python_configuration(self):
        for language in ('java','python'):
            m,d=configured(language)
            p={'schema':'wheel-postgres-service-policy-v1','manifest_sha256':digest(m),'allowed_images':[m['projects'][0]['image']],
               'max_repetitions':2,'total_timeout_seconds':300}
            admit_database(m,d,p,2)
            m['observers'][0]['row_limit']=1
            with self.assertRaisesRegex(AdmissionError,'Unreviewed'):
                admit_database(m,d,p,2)

    def test_unreviewed_image_and_missing_observer_rejected(self):
        for change in [lambda m:m.update(observers=[]),lambda m:m['dependencies'][0].update(port=1234)]:
            m,d,p=self.config();change(m);p['manifest_sha256']=digest(m)
            with self.assertRaises(AdmissionError):admit_database(m,d,p,1)
        m,d,p=self.config();p['allowed_images']=['other@sha256:'+'b'*64]
        with self.assertRaises(AdmissionError):admit_database(m,d,p,1)

    def test_seed_paths_and_sizes_checked_before_docker(self):
        m,_,_=self.config()
        for files in [{},{'fixtures/seed.sql':b'x'*60001},{'fixtures/seed.sql':b'\xff'}]:
            with patch('preflight.postgres_lifecycle.docker',side_effect=AssertionError('No Docker')):
                with self.assertRaises(AdmissionError):validate_seeds(m,{'baseline':files,'candidate':files})

    def test_bindings_use_app_identity_only_and_redact_disposable_passwords(self):
        m,_,_=self.config()
        world=PostgresWorld(m,{},'net','id',lambda:5);world.address='172.18.0.2'
        m['projects'][0]['service']['environment_bindings']=[{'variable':'DB_PASS','dependency':'db','field':'ephemeral_password'}]
        self.assertEqual(world.bindings(),['--env','DB_PASS='+world.app])
        self.assertNotEqual(world.app,world.admin)
        self.assertNotEqual(world.reader,world.admin)
        self.assertNotIn(world.app,world.sanitize(world.app+' '+world.reader+' '+world.admin))

    def test_snapshot_row_overflow_is_execution_error_not_truncated_success(self):
        from preflight.isolated_executor import ExecutionError
        m,_,_=self.config();m['observers'][0]['row_limit']=1
        world=PostgresWorld(m,{},'net','id',lambda:5)
        with patch.object(world,'sql',return_value={'output':'on:repeatable read\n[{"id":1},{"id":2}]'}),self.assertRaisesRegex(ExecutionError,'incomplete'):
            world.snapshot()

    def test_snapshot_is_read_only_and_hashes_recorded_state(self):
        m,_,_=self.config();world=PostgresWorld(m,{},'net','id',lambda:5)
        with patch.object(world,'sql',return_value={'output':'on:repeatable read\n[{"id":1}]'}) as sql:
            result=world.snapshot()
        self.assertTrue(sql.call_args.args[0].startswith('BEGIN ISOLATION LEVEL REPEATABLE READ READ ONLY;'))
        self.assertEqual(sql.call_args.kwargs['role'],'wheel_observer')
        self.assertEqual(result['sha256'],digest(result['state']))


if __name__=='__main__':unittest.main()
