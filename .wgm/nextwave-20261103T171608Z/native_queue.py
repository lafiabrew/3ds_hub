#!/usr/bin/env python3
"""Two native jobs; reuse reviewed process-group owner, durable owned receipts."""
import fcntl
import json
from pathlib import Path
import sys
import time
import uuid
from agent import RUN, candidate_root, check_log_root, core

class Raw:
 def feed(self,data,now):pass
 def eof(self):pass
class Tee:
 def __init__(self,out):self.out=out
 def write(self,data):self.out.write(data);sys.stdout.buffer.write(data)
 def flush(self):self.out.flush();sys.stdout.buffer.flush()

def main(argv):
 if argv[:1]==['--']:argv=argv[1:]
 if not argv:raise SystemExit('usage: native_queue.py -- COMMAND [ARG...]')
 root=check_log_root(RUN/'runtime/build-slots',candidate_root());root.mkdir(parents=True,exist_ok=True)
 handles=[(root/f'slot-{n}.lock').open('a') for n in range(2)];selected=None;start=time.monotonic()
 try:
  while selected is None:
   if (root/'STOP').exists():raise SystemExit('queue blocked by retained cleanup ownership')
   for handle in handles:
    try:fcntl.flock(handle,fcntl.LOCK_EX|fcntl.LOCK_NB);selected=handle;break
    except BlockingIOError:pass
   if selected is None:
    if time.monotonic()-start>1800:raise SystemExit('queue wait deadline; job not started')
    time.sleep(.05)
  if (root/'STOP').exists():raise SystemExit('queue blocked after acquisition')
  ident=uuid.uuid4().hex;wait=time.monotonic()-start;owner=core.OwnedProcess(root/(ident+'.ownership.json'),5,5)
  with (root/(ident+'.log')).open('wb') as out:state=owner.run(argv,Tee(out),sys.stderr,Raw(),1800)
  (root/(ident+'.job.json')).write_text(json.dumps({'queue_wait_s':wait,**state})+'\n')
  if state['pid'] is None:return 127
  if not state['cleanup_complete']:
   (root/'STOP').write_text('retained owned cleanup receipt '+ident+'\n');return 124
  if state['cleanup_reason'] is not None or state['cancel_signal'] is not None:return 1
  code=state['process_rc'];return code if code>=0 else 128-code
 finally:
  for handle in handles:handle.close()

if __name__=='__main__':raise SystemExit(main(sys.argv[1:]))
