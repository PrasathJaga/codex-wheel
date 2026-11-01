"""Authored dependency-consumption controls, not dependency resolution or AI evaluation."""
import argparse
import copy
import hashlib
import json
from pathlib import Path

from preflight.dependency_bundle import acquire
from preflight.executor_smoke import pack
from preflight.isolated_executor import run_pair
from preflight.petclinic_adapter import digest
from preflight.project_discovery import discover_pair


def exercise(language, image, output, controls):
    output.mkdir(parents=True,exist_ok=False)
    if language=='python':
        files={'pyproject.toml':'[project]\nname="dependency-control"\nversion="0.0.0"',
               'test_package.py':'''import sys,unittest,pathlib
sys.path.insert(0,'.deps')
import packaging
from packaging.version import Version
class PackageControl(unittest.TestCase):
 def test_package(self):
  self.assertEqual(packaging.__version__,'24.2')
  self.assertGreater(Version('2.0'),Version('1.0'))
  self.assertTrue(str(pathlib.Path(packaging.__file__).resolve()).startswith('/work/.deps/'))
  with self.assertRaises(OSError) as caught:pathlib.Path('/dependencies/forbidden').write_text('bad')
  self.assertEqual(caught.exception.errno,30)
'''}
        build=[{'argv':['python','-m','pip','install','--no-index','--no-deps','--disable-pip-version-check','--no-cache-dir','--no-compile',
                        '--target','/work/.deps','/dependencies/python/wheels/packaging-24.2-py3-none-any.whl'],'timeout_seconds':90}]
        argv=['python','-m','unittest','discover','-v']
    else:
        files={'pom.xml':'<project><modelVersion>4.0.0</modelVersion><groupId>control</groupId><artifactId>dependency</artifactId><version>0</version></project>',
               'Control.java':'''import java.nio.file.*;
class Control {public static void main(String[] args) throws Exception {
 var c=Class.forName("org.junit.Test");
 if(!c.isAnnotation())throw new AssertionError("JUnit annotation not loaded");
 if(!c.getProtectionDomain().getCodeSource().getLocation().getPath().startsWith("/dependencies/"))throw new AssertionError("wrong JAR");
 try {Files.writeString(Path.of("/dependencies/forbidden"),"bad");throw new AssertionError("writable dependencies");}
 catch(java.nio.file.FileSystemException expected){}
 System.out.println("Loaded reviewed JUnit class from read-only dependency volume");
}}'''}
        build=[]
        argv=['java','--class-path','/dependencies/maven/repository/junit/junit/4.13.2/junit-4.13.2.jar','Control.java']
    baseline=candidate=pack(files)
    source={'baseline_sha256':hashlib.sha256(baseline).hexdigest(),'candidate_sha256':hashlib.sha256(candidate).hexdigest(),
            'baseline_root':'source','candidate_root':'source'}
    discovery=discover_pair(baseline,candidate,source['baseline_sha256'],source['candidate_sha256'],'source','source')
    # Same fixed public artifact controls; new lock explicitly binds this authored source pair.
    lock=copy.deepcopy(controls['lock']);lock['discovery_sha256']=digest(discovery)
    acquisition=copy.deepcopy(controls['policy']);acquisition['lock_sha256']=digest(lock)
    fetched=acquire(lock,acquisition,output/'acquisition')
    assert fetched['status']=='artifacts_verified',fetched
    bundle=(output/'acquisition/dependencies.tar.gz').read_bytes()
    manifest={'schema':'wheel-execution-manifest-v1','discovery_sha256':digest(discovery),
              'projects':[{'id':'control','root':'.','language':language,'image':image,'build':build,
                           'test':[{'argv':argv,'timeout_seconds':90}],'service':None}],
              'dependencies':[],'observers':[],
              'limits':{'cpu_millis':1000,'memory_mb':512,'pids':128,'world_timeout_seconds':180},
              'network':{'build':'reviewed_dependency_fetch_only','runtime':'internal_only'},'reset':'fresh_environment_per_world'}
    policy={'schema':'wheel-dependency-execution-policy-v1','manifest_sha256':digest(manifest),'allowed_images':[image],
            'max_repetitions':2,'total_timeout_seconds':600,'dependency_lock_sha256':digest(lock),
            'dependency_bundle_sha256':hashlib.sha256(bundle).hexdigest()}
    report=run_pair(baseline,candidate,source,manifest,policy,output/'execution',2,
                    dependency={'archive':bundle,'lock':lock,'acquisition_policy':acquisition})
    for name,value in [('manifest',manifest),('policy',policy),('lock',lock),('acquisition-policy',acquisition),('source',source)]:
        (output/(name+'.json')).write_text(json.dumps(value,indent=2)+'\n')
    assert report['status']=='build_and_tests_passed',report
    assert len(report['worlds'])==4 and not report['cleanup_errors']
    return {'language':language,'status':report['status'],'worlds':4,'dependency_closure_verified':False}


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--python-image',required=True);p.add_argument('--java-image',required=True)
    p.add_argument('--output',type=Path,required=True);args=p.parse_args();args.output.mkdir(parents=True,exist_ok=False)
    controls=json.loads(Path('evaluation/dependency_acquisition_controls_v1.json').read_text())
    results=[]
    for language,image in [('python',args.python_image),('java',args.java_image)]:
        results.append(exercise(language,image,args.output/language,controls))
    (args.output/'summary.json').write_text(json.dumps({'kind':'authored_dependency_consumption_controls','results':results,'model_requests':0},indent=2)+'\n')
    print(json.dumps(results))


if __name__=='__main__':main()
