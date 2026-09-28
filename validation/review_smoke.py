import sys,queue,time,json,resource
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1] / 'src'))
from pipeline import PipelineWorker
from backend import load_backend
w=PipelineWorker('Chinese',queue.Queue());t=time.monotonic();load_backend(w)
print(json.dumps({'load_seconds':time.monotonic()-t}),flush=True)
w._correct_and_translate('The microphone is ready.',True)
cases=['The assignment is not due on Friday.','Select option B, not option D.','The value is 28.5 percent, not 25 percent.','Dr. Nguyen will meet Elizabeth at 3:15 p.m.','Do not submit more than two files.','Ancestry and nationality are different concepts.']
for language in ['Chinese','Vietnamese']:
 w.set_target_language(language)
 for raw in cases:
  t=time.monotonic();english,translated,_=w._correct_and_translate(raw,True)
  print(json.dumps({'language':language,'raw':raw,'english':english,'translation':translated,'lexical_preserved':w._preserves_lexical_content(raw,english),'seconds':round(time.monotonic()-t,3)},ensure_ascii=False),flush=True)
print(json.dumps({'peak_rss_kib':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss}),flush=True)
