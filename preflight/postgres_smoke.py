"""Authored database lifecycle controls, not discovery or business verification."""
import argparse
import hashlib
import json
from pathlib import Path

from preflight.executor_smoke import pack
from preflight.petclinic_adapter import digest
from preflight.project_discovery import discover_pair
from preflight.service_executor import run_service_pair

PYTHON_SERVICE = '''import os,socket,struct
from http.server import BaseHTTPRequestHandler,HTTPServer
assert 'MODEL_API_KEY' not in os.environ and 'GITHUB_TOKEN' not in os.environ
s=socket.create_connection((os.environ['DB_HOST'],int(os.environ['DB_PORT'])),timeout=5)
f=s.makefile('rb')
def send(t,b):s.sendall(t+struct.pack('!I',len(b)+4)+b)
def read():
 t=f.read(1)
 if not t: raise RuntimeError('database disconnected')
 n=struct.unpack('!I',f.read(4))[0]
 return t,f.read(n-4)
b=struct.pack('!I',196608)+b'user\\0'+os.environ['DB_USER'].encode()+b'\\0database\\0wheel\\0\\0'
s.sendall(struct.pack('!I',len(b)+4)+b)
while True:
 t,b=read()
 if t==b'R' and struct.unpack('!I',b[:4])[0]==3:send(b'p',os.environ['DB_PASS'].encode()+b'\\0')
 if t==b'E':raise RuntimeError('database authentication error')
 if t==b'Z':break
send(b'Q',b"INSERT INTO public.events VALUES (2,'service');\\0")
while True:
 t,b=read()
 if t==b'E':raise RuntimeError('database write error')
 if t==b'Z':break
s.close()
class Handler(BaseHTTPRequestHandler):
 def do_GET(self):
  self.send_response(200);self.end_headers();self.wfile.write(b'healthy')
HTTPServer(('0.0.0.0',8080),Handler).serve_forever()
'''
JAVA_SERVICE = '''import java.io.*;import java.net.*;import java.nio.charset.StandardCharsets;
import com.sun.net.httpserver.HttpServer;
class Server {
 static DataInputStream in;static DataOutputStream out;
 static byte[] z(String s){return (s+"\\0").getBytes(StandardCharsets.UTF_8);}
 static void send(int t,byte[] b)throws Exception{out.writeByte(t);out.writeInt(b.length+4);out.write(b);out.flush();}
 static void ready()throws Exception{while(true){int t=in.readUnsignedByte();int n=in.readInt();byte[] b=in.readNBytes(n-4);
 if(t=='E')throw new RuntimeException("database error");
 if(t=='R'&&java.nio.ByteBuffer.wrap(b).getInt()==3)send('p',z(System.getenv("DB_PASS")));
 if(t=='Z')return;}}
 public static void main(String[] args)throws Exception{
 if(System.getenv("MODEL_API_KEY")!=null||System.getenv("GITHUB_TOKEN")!=null)throw new RuntimeException("credential");
 try(Socket socket=new Socket(System.getenv("DB_HOST"),Integer.parseInt(System.getenv("DB_PORT")))){
 socket.setSoTimeout(5000);in=new DataInputStream(socket.getInputStream());out=new DataOutputStream(socket.getOutputStream());
 var buffer=new ByteArrayOutputStream();var data=new DataOutputStream(buffer);data.writeInt(196608);
 data.write(z("user"));data.write(z(System.getenv("DB_USER")));data.write(z("database"));data.write(z("wheel"));data.writeByte(0);
 out.writeInt(buffer.size()+4);out.write(buffer.toByteArray());out.flush();ready();
 send('Q',z("INSERT INTO public.events VALUES (2,'service');"));ready();}
 HttpServer server=HttpServer.create(new InetSocketAddress("0.0.0.0",8080),0);
 server.createContext("/health",exchange->{byte[] b="healthy".getBytes();exchange.sendResponseHeaders(200,b.length);try(var o=exchange.getResponseBody()){o.write(b);}});server.start();
 }
}'''


def exercise(language,image,db_image,output,bad_candidate=False,overflow=False):
    if language=='python':
        files={'pyproject.toml':'[project]\nname="database-control"\nversion="0"',
               'test_ok.py':'import unittest\nclass Check(unittest.TestCase):\n def test_ok(self):self.assertTrue(True)\n',
               'server.py':PYTHON_SERVICE}
        test,start,badfile=['python','-m','unittest','discover'],['python','-u','server.py'],'server.py'
    else:
        files={'pom.xml':'<project/>','Check.java':'class Check{public static void main(String[] a){}}','Server.java':JAVA_SERVICE}
        test,start,badfile=['java','Check.java'],['java','Server.java'],'Server.java'
    files['seed.sql']="CREATE TABLE public.events(id integer PRIMARY KEY, value text); INSERT INTO public.events VALUES(1,'seed');"
    changed=dict(files)
    if bad_candidate:
        changed[badfile]='raise RuntimeError("startup control")' if language=='python' else 'class Server{public static void main(String[] a){throw new RuntimeException("startup control");}}'
    base,head=pack(files),pack(changed)
    source={'baseline_sha256':hashlib.sha256(base).hexdigest(),'candidate_sha256':hashlib.sha256(head).hexdigest(),
            'baseline_root':'source','candidate_root':'source'}
    discovery=discover_pair(base,head,source['baseline_sha256'],source['candidate_sha256'],'source','source')
    manifest={'schema':'wheel-execution-manifest-v1','discovery_sha256':digest(discovery),
              'projects':[{'id':'api','root':'.','language':language,'image':image,'build':[],
                           'test':[{'argv':test,'timeout_seconds':60}],
                           'service':{'start':{'argv':start,'timeout_seconds':60},'port':8080,
                                      'health':{'path':'/health','status':200,'timeout_seconds':30},
                                      'environment_bindings':[{'variable':var,'dependency':'db','field':field} for var,field in
                                                              [('DB_HOST','host'),('DB_PORT','port'),('DB_USER','username'),('DB_PASS','ephemeral_password')]]}}],
              'dependencies':[{'id':'db','kind':'postgres','image':db_image,'port':5432,'seed_files':['seed.sql']}],
              'observers':[{'id':'state','kind':'postgres_read_only_snapshot','dependency':'db','tables':['events'],'row_limit':1 if overflow else 10}],
              'limits':{'cpu_millis':1000,'memory_mb':512,'pids':128,'world_timeout_seconds':180},
              'network':{'build':'reviewed_dependency_fetch_only','runtime':'internal_only'},'reset':'fresh_environment_per_world'}
    policy={'schema':'wheel-postgres-service-policy-v1','manifest_sha256':digest(manifest),'allowed_images':[image,db_image],
            'max_repetitions':2,'total_timeout_seconds':900}
    result=run_service_pair(base,head,source,manifest,policy,output,repetitions=1 if bad_candidate or overflow else 2,postgres=True)
    for name,value in [('source',source),('manifest',manifest),('policy',policy)]:
        (Path(output)/(name+'.json')).write_text(json.dumps(value,indent=2)+'\n')
    expected='execution_error' if overflow else 'candidate_lifecycle_failed' if bad_candidate else 'service_lifecycle_passed'
    assert result['status']==expected,(result['status'],result.get('error'))
    assert not result['cleanup_errors'],result['cleanup_errors']
    if overflow:
        assert 'row limit' in result.get('error','')
    else:
        seeds=[]
        for world in result['worlds']:
            assert world['database']['observer_write_rejected']
            initial=world['snapshots']['initial'];seeds.append(initial['sha256'])
            assert initial['state']['state']['events']==[{'id':1,'value':'seed'}]
            if world['status']=='service_ready':
                assert len(world['snapshots']['after_health']['state']['state']['events'])==2
                assert world['snapshots']['after_health']['sha256']==world['snapshots']['after_stop']['sha256']
        assert len(set(seeds))==1
    return {'language':language,'expected':expected,'observed':result['status'],'worlds':len(result['worlds'])}


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ['python-image','java-image','postgres-image']:p.add_argument('--'+name,required=True)
    p.add_argument('--output',type=Path,required=True)
    args=p.parse_args();args.output.mkdir(parents=True,exist_ok=False)
    rows=[]
    for lang,image in [('python',args.python_image),('java',args.java_image)]:
        rows.append(exercise(lang,image,args.postgres_image,args.output/(lang+'-healthy')))
        rows.append(exercise(lang,image,args.postgres_image,args.output/(lang+'-startup-failure'),bad_candidate=True))
    rows.append(exercise('python',args.python_image,args.postgres_image,args.output/'observer-overflow',overflow=True))
    (args.output/'summary.json').write_text(json.dumps({'kind':'authored_postgres_lifecycle_controls','results':rows,'model_requests':0,
                                                     'business_behavior_verified':False},indent=2)+'\n')
    print(json.dumps(rows))


if __name__=='__main__':main()
