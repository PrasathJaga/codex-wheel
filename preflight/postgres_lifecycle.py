"""Disposable Postgres and independent read-only observation, no business oracle."""
import json
from pathlib import PurePosixPath
from secrets import token_hex
import time

from preflight.execution_manifest import validate_manifest, image, integer
from preflight.isolated_executor import checked, docker, ExecutionError
from preflight.petclinic_adapter import AdmissionError, digest, exact


def admit_database(manifest, discovery, policy, repetitions):
    validate_manifest(manifest, discovery)
    exact(policy, {'schema','manifest_sha256','allowed_images','max_repetitions','total_timeout_seconds'})
    if policy['schema'] != 'wheel-postgres-service-policy-v1' or policy['manifest_sha256'] != digest(manifest):
        raise AdmissionError('Unreviewed database service manifest')
    integer(policy['max_repetitions'],1,3)
    integer(repetitions,1,policy['max_repetitions'])
    integer(policy['total_timeout_seconds'],10,1800)
    if type(policy['allowed_images']) is not list or not 1 <= len(policy['allowed_images']) <= 8:
        raise AdmissionError('Trusted image list required')
    for item in policy['allowed_images']:
        image(item)
    if (len(manifest['projects']) != 1 or manifest['projects'][0]['service'] is None
            or len(manifest['dependencies']) != 1 or manifest['dependencies'][0]['kind'] != 'postgres'
            or not manifest['observers']):
        raise AdmissionError('Requires one HTTP service, one Postgres and read-only observers')
    project, dependency = manifest['projects'][0], manifest['dependencies'][0]
    if dependency['port'] != 5432 or any(i not in policy['allowed_images'] for i in (project['image'],dependency['image'])):
        raise AdmissionError('Requires reviewed images and Postgres port 5432')
    for command in project['build'] + project['test'] + [project['service']['start']]:
        if command['argv'][0].startswith('./'):
            raise AdmissionError('Repository wrappers unsupported')
    for observer in manifest['observers']:
        if observer['dependency'] != dependency['id']:
            raise AdmissionError('Unresolved database observer')


def validate_seeds(manifest, admitted):
    for files in admitted.values():
        for path in manifest['dependencies'][0]['seed_files']:
            if path not in files or len(files[path]) > 60000 or b'\x00' in files[path]:
                raise AdmissionError('Missing/oversized/invalid seed SQL')
            try:
                files[path].decode('utf-8')
            except UnicodeError as error:
                raise AdmissionError('Seed SQL must be UTF-8') from error


class PostgresWorld:
    def __init__(self, manifest, files, network, identity, budget):
        self.manifest,self.files,self.network,self.name,self.budget = manifest,files,network,identity+'-db',budget
        self.dependency=manifest['dependencies'][0]
        self.admin,self.app,self.reader=token_hex(24),token_hex(24),token_hex(24)
        self.address=None

    def sanitize(self, value):
        for secret in (self.admin,self.app,self.reader):
            value=value.replace(secret,'[DISPOSABLE_PASSWORD_REDACTED]')
        return value

    def sql(self, statement, role='wheel_admin', check=True):
        result=docker(['exec',self.name,'psql','-X','-qAt','-v','ON_ERROR_STOP=1','-U',role,'-d','wheel','-c',statement],self.budget())
        if check and result['returncode']:
            raise ExecutionError('Postgres operation failed',self.sanitize(result['output']))
        return result

    def start(self):
        from preflight.service_executor import endpoint
        limits=self.manifest['limits']
        checked(['create','--name',self.name,'--pull','never','--network',self.network,'--read-only','--user','999:999',
                 '--cap-drop','ALL','--security-opt','no-new-privileges','--cpus',str(limits['cpu_millis']/1000),
                 '--memory',str(limits['memory_mb'])+'m','--memory-swap',str(limits['memory_mb'])+'m','--pids-limit',str(limits['pids']),
                 '--tmpfs','/tmp:rw,uid=999,gid=999,size=64m','--tmpfs','/var/run/postgresql:rw,uid=999,gid=999,size=16m',
                 '--tmpfs','/var/lib/postgresql/data:rw,uid=999,gid=999,size=256m',
                 '--env','POSTGRES_USER=wheel_admin','--env','POSTGRES_PASSWORD='+self.admin,
                 '--env','POSTGRES_DB=wheel','--env','POSTGRES_HOST_AUTH_METHOD=password',self.dependency['image']],self.budget())
        record=json.loads(checked(['inspect',self.name],self.budget()))[0]
        host=record['HostConfig']
        if (not host['ReadonlyRootfs'] or host['NetworkMode']!=self.network or host.get('Mounts') or host.get('Binds')
                or host.get('Privileged') or host.get('CapAdd') or host.get('CapDrop')!=['ALL'] or record['Config']['User']!='999:999'):
            raise ExecutionError('Database isolation mismatch')
        checked(['start',self.name],self.budget())
        self.address=endpoint(self.name,self.network)
        while True:
            result=docker(['exec',self.name,'pg_isready','-h','127.0.0.1','-U','wheel_admin','-d','wheel'],self.budget())
            if not result['returncode']:
                break
            state=json.loads(checked(['inspect','--format','{{json .State}}',self.name],self.budget()))
            if not state['Running'] or state.get('OOMKilled'):
                raise ExecutionError('Database startup failed')
            time.sleep(min(0.2,self.budget()))
        for path in self.dependency['seed_files']:
            self.sql(self.files[path].decode())
        self.sql("CREATE ROLE wheel_app LOGIN PASSWORD '"+self.app+"'; CREATE ROLE wheel_observer LOGIN PASSWORD '"+self.reader+"'; GRANT CONNECT ON DATABASE wheel TO wheel_app,wheel_observer; GRANT USAGE ON SCHEMA public TO wheel_app,wheel_observer; GRANT SELECT,INSERT,UPDATE,DELETE ON ALL TABLES IN SCHEMA public TO wheel_app; GRANT USAGE,SELECT ON ALL SEQUENCES IN SCHEMA public TO wheel_app;")
        tables=sorted({t for o in self.manifest['observers'] for t in o['tables']})
        for table in tables:
            kind=self.sql("SELECT relkind::text || ':' || relrowsecurity::text FROM pg_class WHERE oid='public.\""+table+"\"'::regclass;")['output'].strip()
            if kind!='r:false':
                raise ExecutionError('Observer requires ordinary tables without row-level security')
            self.sql('GRANT SELECT ON public."'+table+'" TO wheel_observer;')
            writable=self.sql("SELECT has_table_privilege('wheel_observer','public.\""+table+"\"','INSERT,UPDATE,DELETE,TRUNCATE,REFERENCES,TRIGGER') OR has_schema_privilege('wheel_observer','public','CREATE');")['output'].strip()
            if writable!='f':
                raise ExecutionError('Observer has write or schema creation privileges')
        roles=self.sql("SELECT rolsuper OR rolcreaterole OR rolcreatedb OR rolbypassrls OR EXISTS(SELECT FROM pg_auth_members WHERE member=pg_roles.oid) FROM pg_roles WHERE rolname='wheel_observer';")['output'].strip()
        if roles!='f':
            raise ExecutionError('Observer role has elevated permissions')
        writes=self.sql('BEGIN READ ONLY; DELETE FROM public."'+tables[0]+'" WHERE false; ROLLBACK;',role='wheel_observer',check=False)
        if writes['returncode']==0:
            raise ExecutionError('Observer write probe unexpectedly succeeded')
        return {'container':self.name,'network':self.network,'read_only_root':True,'user':'999:999',
                'host_mounts':False,'observer_role':'wheel_observer','observer_write_rejected':True,
                'seed_sha256':digest({p:self.files[p].decode() for p in self.dependency['seed_files']})}

    def bindings(self):
        values={'host':self.address,'port':'5432','database':'wheel','username':'wheel_app','ephemeral_password':self.app}
        return sum((['--env',b['variable']+'='+values[b['field']]] for b in self.manifest['projects'][0]['service']['environment_bindings']),[])

    def snapshot(self):
        requested=[]
        statements=["SELECT current_setting('transaction_read_only') || ':' || current_setting('transaction_isolation');"]
        for observer in self.manifest['observers']:
            for table in observer['tables']:
                requested.append((observer['id'],table,observer['row_limit']))
                statements.append('SELECT coalesce(jsonb_agg(to_jsonb(t) ORDER BY to_jsonb(t)::text),\'[]\'::jsonb) FROM (SELECT * FROM public."'+table+'" LIMIT '+str(observer['row_limit']+1)+') t;')
        sql='BEGIN ISOLATION LEVEL REPEATABLE READ READ ONLY; '+''.join(statements)+' COMMIT;'
        lines=self.sql(sql,role='wheel_observer')['output'].strip().splitlines()
        if len(lines)!=len(requested)+1 or lines[0]!='on:repeatable read':
            raise ExecutionError('Snapshot transaction isolation/evidence mismatch')
        result={}
        for (observer,table,limit),line in zip(requested,lines[1:]):
            rows=json.loads(line)
            if len(rows)>limit:
                raise ExecutionError('Observer row limit exceeded; snapshot incomplete')
            result.setdefault(observer,{})[table]=rows
        return {'state':result,'sha256':digest(result),'role':'wheel_observer',
                'transaction_read_only':True,'isolation':'repeatable read'}
