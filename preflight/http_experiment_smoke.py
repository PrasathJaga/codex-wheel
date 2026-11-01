"""Authored HTTP contract execution controls, not model or transfer evaluation."""
import argparse
import hashlib
import json
from pathlib import Path

from preflight.executor_smoke import pack
from preflight.petclinic_adapter import digest
from preflight.project_discovery import discover_pair
from preflight.service_executor import run_service_pair
from preflight.http_experiment import tool_schema


def exercise(language,image,output,violating=False,invalid_baseline=False):
    if language=='python':
        filename='server.py'
        server='''from http.server import BaseHTTPRequestHandler, HTTPServer
class Handler(BaseHTTPRequestHandler):
 def do_GET(self):
  body=b'healthy' if self.path=='/health' else b'{"value":4}'
  self.send_response(200);self.end_headers();self.wfile.write(body)
HTTPServer(('0.0.0.0',8080),Handler).serve_forever()
'''
        files={'pyproject.toml':'[project]\nname="http-execution-control"\nversion="0"',filename:server}
        test=['python','-m','py_compile',filename]; start=['python',filename]
    else:
        filename='Server.java'
        server='''import com.sun.net.httpserver.HttpServer;import java.net.*;
class Server { public static void main(String[] args) throws Exception {
 HttpServer server=HttpServer.create(new InetSocketAddress("0.0.0.0",8080),0);
 server.createContext("/health",e->{byte[] b="healthy".getBytes();e.sendResponseHeaders(200,b.length);e.getResponseBody().write(b);e.close();});
 server.createContext("/value",e->{byte[] b="{\\"value\\":4}".getBytes();e.sendResponseHeaders(200,b.length);e.getResponseBody().write(b);e.close();});
 server.start();
} }
'''
        files={'pom.xml':'<project/>',filename:server}
        test=['java','--version']; start=['java','--add-modules','jdk.httpserver',filename]
    wrong=server.replace('value\\":4','value\\":5') if language=='java' else server.replace('"value":4','"value":5')
    assert wrong!=server
    base_files=dict(files); candidate_files=dict(files)
    if invalid_baseline: base_files[filename]=wrong
    if violating: candidate_files[filename]=wrong
    baseline,candidate=pack(base_files),pack(candidate_files)
    source={'baseline_sha256':hashlib.sha256(baseline).hexdigest(),'candidate_sha256':hashlib.sha256(candidate).hexdigest(),
            'baseline_root':'source','candidate_root':'source'}
    discovery=discover_pair(baseline,candidate,source['baseline_sha256'],source['candidate_sha256'],'source','source')
    manifest={'schema':'wheel-execution-manifest-v1','discovery_sha256':digest(discovery),
              'projects':[{'id':'service','root':'.','language':language,'image':image,'build':[],
                           'test':[{'argv':test,'timeout_seconds':60}],
                           'service':{'start':{'argv':start,'timeout_seconds':90},'port':8080,
                                      'health':{'path':'/health','status':200,'timeout_seconds':40},'environment_bindings':[]}}],
              'dependencies':[],'observers':[],'limits':{'cpu_millis':1000,'memory_mb':512,'pids':128,'world_timeout_seconds':180},
              'network':{'build':'reviewed_dependency_fetch_only','runtime':'internal_only'},'reset':'fresh_environment_per_world'}
    lifecycle={'schema':'wheel-service-execution-policy-v1','manifest_sha256':digest(manifest),'allowed_images':[image],
               'max_repetitions':2,'total_timeout_seconds':600}
    interface={'schema':'wheel-http-interface-v1','manifest_sha256':digest(manifest),
               'operations':[{'id':'read_value','method':'GET','path':'/value','body_schema':None,
                              'source_refs':[{'side':side,'path':filename,'line_start':1,'line_end':min(5,len(server.splitlines()))} for side in ('baseline','candidate')]}]}
    contract={'schema':'wheel-http-contract-v1','manifest_sha256':digest(manifest),
              'provenance':{'kind':'developer_declared','reference':'Authored runtime control: /value returns integer value 4'},
              'checks':[{'operation':'read_value','statuses':[200],'json_equals':[{'path':['value'],'value':4}]}]}
    plan={'schema':'wheel-http-experiment-v1','interface_sha256':digest(interface),'contract_sha256':digest(contract),
          'actions':[{'operation':'read_value','body':None}]}
    experiment={'interface':interface,'contract':contract,'plan':plan,
                'policy':{'schema':'wheel-http-experiment-policy-v1','lifecycle_policy_sha256':digest(lifecycle),
                          'interface_sha256':digest(interface),'contract_sha256':digest(contract),'plan_sha256':digest(plan)}}
    result=run_service_pair(baseline,candidate,source,manifest,lifecycle,output,repetitions=2,experiment=experiment)
    expected='baseline_invalid' if invalid_baseline else 'confirmed_contract_violation' if violating else 'no_violation_observed'
    assert result['status']==expected,(result['status'],result.get('error'))
    assert not result['cleanup_errors']
    assert all(w['health_attempts'][-1]['status']==200 for w in result['worlds'])
    assert all(w['experiment']['events'][0]['response']['status']==200 for w in result['worlds'])
    assert all(w['stopped_before_cleanup'] for w in result['worlds'])
    for name,value in [('source',source),('manifest',manifest),('policy',lifecycle),('tool-schema',tool_schema(interface,contract))]:
        (Path(output)/(name+'.json')).write_text(json.dumps(value,indent=2)+'\n')
    return {'language':language,'status':result['status'],'worlds':len(result['worlds']),'meta_calls':0}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--python-image',required=True);parser.add_argument('--java-image',required=True)
    parser.add_argument('--output',type=Path,required=True);args=parser.parse_args()
    args.output.mkdir(parents=True,exist_ok=False);rows=[]
    for language,image in [('python',args.python_image),('java',args.java_image)]:
        rows.append(exercise(language,image,args.output/(language+'-preserving')))
        rows.append(exercise(language,image,args.output/(language+'-violating'),violating=True))
    rows.append(exercise('python',args.python_image,args.output/'invalid-baseline',invalid_baseline=True))
    (args.output/'summary.json').write_text(json.dumps({'kind':'authored_http_execution_controls','results':rows,'model_requests':0},indent=2)+'\n')
    print(json.dumps(rows))


if __name__=='__main__': main()
