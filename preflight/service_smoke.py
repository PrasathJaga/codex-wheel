"""Authored lifecycle controls only; not an unfamiliar-project benchmark."""
import argparse
import hashlib
import json
from pathlib import Path

from preflight.executor_smoke import pack
from preflight.petclinic_adapter import digest
from preflight.project_discovery import discover_pair
from preflight.service_executor import run_service_pair


def exercise(language, image, output, bad_candidate=False, bad_baseline=False):
    if language == 'python':
        files = {'pyproject.toml': '[project]\nname="lifecycle-control"\nversion="0"',
                 'test_control.py': 'import unittest\nclass Check(unittest.TestCase):\n def test_ok(self): self.assertEqual(2+2,4)\n',
                 'server.py': '''import os, pathlib
from http.server import BaseHTTPRequestHandler,HTTPServer
assert 'MODEL_API_KEY' not in os.environ and 'GITHUB_TOKEN' not in os.environ
assert not pathlib.Path('/var/run/docker.sock').exists()
assert not pathlib.Path('/work/preflight').exists()
assert not pathlib.Path('/tmp/world-marker').exists()
pathlib.Path('/tmp/world-marker').write_text('fresh')
class Handler(BaseHTTPRequestHandler):
 def do_GET(self):
  self.send_response(200 if self.path=='/health' else 404)
  self.end_headers()
  self.wfile.write(b'healthy lifecycle control')
HTTPServer(('0.0.0.0',8080),Handler).serve_forever()
'''}
        test, start = ['python', '-m', 'unittest', 'discover', '-v'], ['python', '-u', 'server.py']
        bad_file = 'server.py'
    else:
        files = {'pom.xml': '<project><modelVersion>4.0.0</modelVersion><groupId>control</groupId><artifactId>service</artifactId><version>0</version></project>',
                 'Check.java': 'class Check {public static void main(String[] a) {if(2+2!=4)throw new AssertionError();}}',
                 'Server.java': '''import com.sun.net.httpserver.HttpServer;
import java.net.InetSocketAddress;
import java.nio.file.*;
class Server {
 public static void main(String[] args) throws Exception {
  if(System.getenv("MODEL_API_KEY")!=null||System.getenv("GITHUB_TOKEN")!=null)throw new AssertionError("credential");
  if(Files.exists(Path.of("/work/preflight"))||Files.exists(Path.of("/var/run/docker.sock")))throw new AssertionError("mount");
  if(Files.exists(Path.of("/tmp/world-marker")))throw new AssertionError("state");
  Files.writeString(Path.of("/tmp/world-marker"),"fresh");
  HttpServer server=HttpServer.create(new InetSocketAddress("0.0.0.0",8080),0);
  server.createContext("/health", exchange -> {
   byte[] body="healthy lifecycle control".getBytes();
   exchange.sendResponseHeaders(200,body.length);
   try(var out=exchange.getResponseBody()){out.write(body);}
  });
  server.start();
 }
}'''}
        test, start, bad_file = ['java', 'Check.java'], ['java', 'Server.java'], 'Server.java'
    changed = dict(files)
    if bad_candidate or bad_baseline:
        if language == 'python':
            changed[bad_file] = 'raise RuntimeError("intentional service startup control")\n'
        else:
            changed[bad_file] = 'class Server {public static void main(String[] a){throw new RuntimeException("intentional startup control");}}'
    baseline, candidate = pack(changed if bad_baseline else files), pack(changed if bad_candidate else files)
    source = {'baseline_sha256': hashlib.sha256(baseline).hexdigest(), 'candidate_sha256': hashlib.sha256(candidate).hexdigest(),
              'baseline_root': 'source', 'candidate_root': 'source'}
    discovery = discover_pair(baseline,candidate,source['baseline_sha256'],source['candidate_sha256'],'source','source')
    manifest = {'schema': 'wheel-execution-manifest-v1', 'discovery_sha256': digest(discovery),
                'projects': [{'id':'service', 'root':'.', 'language':language, 'image':image, 'build':[],
                              'test':[{'argv':test,'timeout_seconds':60}],
                              'service':{'start':{'argv':start,'timeout_seconds':60},'port':8080,
                                         'health':{'path':'/health','status':200,'timeout_seconds':30},'environment_bindings':[]}}],
                'dependencies':[],'observers':[], 'limits':{'cpu_millis':1000,'memory_mb':512,'pids':128,'world_timeout_seconds':180},
                'network':{'build':'reviewed_dependency_fetch_only','runtime':'internal_only'},'reset':'fresh_environment_per_world'}
    policy={'schema':'wheel-service-execution-policy-v1','manifest_sha256':digest(manifest),'allowed_images':[image],
            'max_repetitions':2,'total_timeout_seconds':600}
    result=run_service_pair(baseline,candidate,source,manifest,policy,output,repetitions=1 if bad_candidate or bad_baseline else 2)
    for name,value in [('source',source),('manifest',manifest),('policy',policy),('discovery',discovery)]:
        (Path(output)/(name+'.json')).write_text(json.dumps(value,indent=2)+'\n')
    expected='baseline_invalid' if bad_baseline else 'candidate_lifecycle_failed' if bad_candidate else 'service_lifecycle_passed'
    assert result['status']==expected,(result['status'],result.get('error'))
    assert not result['cleanup_errors']
    assert len({w['network'] for w in result['worlds']})==len(result['worlds'])
    assert all(w['internal_network_verified'] and w['stopped_before_cleanup'] for w in result['worlds'])
    if bad_baseline:
        assert len(result['worlds'])==1 and result['worlds'][0]['side']=='baseline'
    return {'language':language,'expected':expected,'observed':result['status'],'worlds':len(result['worlds'])}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--python-image',required=True)
    parser.add_argument('--java-image',required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    args.output.mkdir(parents=True,exist_ok=False)
    rows=[]
    for language,image in [('python',args.python_image),('java',args.java_image)]:
        rows.append(exercise(language,image,args.output/(language+'-healthy')))
        rows.append(exercise(language,image,args.output/(language+'-startup-failure'),True))
    rows.append(exercise('python',args.python_image,args.output/'invalid-baseline',bad_baseline=True))
    (args.output/'summary.json').write_text(json.dumps({'kind':'authored_service_lifecycle_controls','results':rows,
                                                     'meta_calls':0,'business_behavior_verified':False},indent=2)+'\n')
    print(json.dumps(rows))


if __name__=='__main__':
    main()
