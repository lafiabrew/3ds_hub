"""Real wrapper subprocess regressions; no model/network calls or fake product evidence."""
import concurrent.futures
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import time
import unittest

RUN=Path(__file__).resolve().parents[1]
AGENT=RUN/'agent.py'
FAKE='''#!/usr/bin/env python3
import json,os,signal,time
mode=os.environ['WAVE_FIXTURE_MODE']
def emit(v): print(json.dumps(v,ensure_ascii=False),flush=True)
emit({'type':'agent_start'});emit({'type':'turn_start'})
if mode=='hang':
 signal.signal(signal.SIGTERM,signal.SIG_IGN)
 while True:time.sleep(.02)
if mode=='flood':
 for n in range(500):emit({'type':'message_update','padding':'x'*200})
else:time.sleep(.02)
emit({'type':'message_end','message':{'role':'assistant','stopReason':'error' if mode=='error' else 'stop','content':[{'type':'text','text':'READY\\u2028雪'}]}})
emit({'type':'turn_end'});emit({'type':'agent_settled','aborted':False})
'''

class AgentBoundary(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory(dir=RUN/'runtime');self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name)
  self.exe=self.root/'fake-pi';self.exe.write_text(FAKE);self.exe.chmod(0o755)
  self.repo=self.root/'repo';self.repo.mkdir();subprocess.run(['git','init','-q',str(self.repo)],check=True)
  self.children=[];self.addCleanup(self.cleanup)
 def cleanup(self):
  for p in self.children:
   if p.poll() is None:p.terminate()
   try:p.wait(timeout=12)
   except subprocess.TimeoutExpired:p.kill();p.wait(timeout=3)
 def launch(self,mode,extra=()):
  label='fixture-'+self.root.name+'-'+mode
  env=dict(os.environ,WAVE_FIXTURE_MODE=mode,PYTHONDONTWRITEBYTECODE='1')
  out=(self.root/(mode+'.out')).open('wb');self.addCleanup(out.close)
  cmd=[sys.executable,str(AGENT),'--lane',label,'--role','fixture','--phase','validation','--executable',str(self.exe),'--timeout','1' if mode=='hang' else '10',*extra,'fixture request']
  p=subprocess.Popen(cmd,cwd=self.repo,env=env,stdout=out,stderr=subprocess.STDOUT);self.children.append(p);return p,label
 def record(self,label):
  rows=[json.loads(x) for x in (RUN/'runtime/agent-metrics.jsonl').read_text().splitlines() if x]
  return next(x for x in reversed(rows) if x['lane']==label)
 def test_mixed_success_and_semantic_process_zero_error(self):
  # One failed sibling must remain failed even though both fake providers exit0.
  good,a=self.launch('good');bad,b=self.launch('error')
  self.assertEqual(good.wait(timeout=10),0);self.assertEqual(bad.wait(timeout=10),1)
  self.assertTrue(self.record(a)['ok']);self.assertFalse(self.record(b)['ok']);self.assertEqual(self.record(b)['process_rc'],0)
  self.assertGreater(self.record(a)['observed_active_turn_s_lower_bound'],0)
 def test_output_loss_is_not_success_shaped_tail(self):
  # Exceeding bounded capture fails even if the child later emits stop/settled.
  p,label=self.launch('flood',['--max-output-bytes','256']);self.assertEqual(p.wait(timeout=12),1)
  row=self.record(label);self.assertTrue(row['evidence_lost']);self.assertFalse(row['ok']);self.assertTrue(row['cleanup_complete'])
 def test_cancel_during_timeout_cleanup_keeps_deadline_and_reaps(self):
  # Real TERM-ignoring child plus a second cancellation cannot restart cleanup forever.
  p,label=self.launch('hang');time.sleep(2);p.terminate()
  self.assertEqual(p.wait(timeout=10),1);row=self.record(label)
  self.assertFalse(row['ok']);self.assertTrue(row['cleanup_complete']);self.assertFalse(row['owned'])
  with self.assertRaises(ProcessLookupError):os.killpg(row['pgid'],0)

if __name__=='__main__':unittest.main()
