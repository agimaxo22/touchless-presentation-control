"""Human-operated live evaluation. Stores predictions and commands, never frames."""
import sys,time,json,csv,queue,threading
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app import App,tk,ttk,np
OUT=Path(__file__).resolve().parent/'runs'/time.strftime('%Y%m%d-%H%M%S')
OUT.mkdir(parents=True,exist_ok=False)
class GuidedTest(App):
 def __init__(self,root):
  self.observations=[];self.trials=[];self.active=False;self.started=False
  self.plan=[(g,4) for g in ['like','palm','fist','peace','no_gesture'] for _ in range(10)]+[('empty_frame',10),('natural_movement',20),('unsupported_gesture',20)]
  super().__init__(root)
  self.root.title('Gesture Lab — Guided Live Evaluation')
  self.guide=tk.StringVar(value='Loading model. Then allow camera access. No video or photos are saved.')
  panel=ttk.Frame(root);panel.pack(fill='x',before=root.winfo_children()[0],padx=20,pady=8)
  ttk.Label(panel,textvariable=self.guide,font=('Helvetica',14,'bold'),wraplength=1000).pack(anchor='w')
  self.next_button=ttk.Button(panel,text='Start next trial',command=self.begin_trial);self.next_button.pack(side='left',pady=5)
  ttk.Button(panel,text='Mark last trial invalid / redo',command=self.redo).pack(side='left',padx=8)
  ttk.Button(panel,text='Save and stop test',command=self.save_stop).pack(side='left')
  root.after(300,self.ready)
 def worker(self):
  try:
   from predictor import Predictor
   p=Predictor();self.results.put(('ready',p))
  except Exception as e:self.results.put(('error',str(e)));return
  while True:
   job=self.jobs.get()
   if job is None:return
   rgb,source=job
   try:
    start=time.monotonic();scores=p.predict(rgb);ended=time.monotonic()
    if source=='camera':
     k=int(np.argmax(scores));self.observations.append({'time':ended,'label':p.classes[k],'score':float(scores[k]),'latency_ms':(ended-start)*1000})
    self.results.put(('prediction',(scores,source,(ended-start)*1000)))
   except Exception as e:self.results.put(('error',str(e)))
 def ready(self):
  if self.predictor is None:self.root.after(300,self.ready);return
  if not self.started:
   self.started=True;self.start_camera();self.command('like','manual');self.prompt()
 def prompt(self):
  if len(self.trials)>=len(self.plan):self.guide.set('Finished. Results saved locally. Camera off.');return
  g,d=self.plan[len(self.trials)];names={'like':'THUMBS UP','palm':'OPEN PALM','fist':'CLOSED FIST','peace':'PEACE SIGN','no_gesture':'NEUTRAL HAND','empty_frame':'EMPTY FRAME (leave the camera view)','natural_movement':'NATURAL MOVEMENT (no intentional commands)','unsupported_gesture':'UNSUPPORTED GESTURE (not one of the five classes)'}
  self.guide.set(f'Trial {len(self.trials)+1}/{len(self.plan)}: {names[g]}. Relax your hand first, then click Start next trial. Hold during the capture.')
 def begin_trial(self):
  if self.active or len(self.trials)>=len(self.plan):return
  if self.cap is None:self.guide.set('Start camera before testing. Allow camera permission if prompted.');return
  self.active=True;self.next_button.state(['disabled']);self.armed.set(False);self.gate.reset();self.countdown(3)
 def countdown(self,n):
  if not self.active:return
  g,d=self.plan[len(self.trials)]
  if n:
   self.guide.set(f'Get ready: {g}. Capture starts in {n} seconds.');self.root.after(1000,lambda:self.countdown(n-1));return
  self.gate.reset();self.armed.set(True);self.trial_start=time.monotonic();self.event_start=len(self.events)
  self.capture_tick(d)
 def capture_tick(self,n):
  if not self.active:return
  g,d=self.plan[len(self.trials)];self.guide.set(f'CAPTURING {g}: {n} seconds remaining. Keep the intended gesture steady.')
  if n:self.root.after(1000,lambda:self.capture_tick(n-1))
  else:self.finish_trial()
 def finish_trial(self):
  end=time.monotonic();g,d=self.plan[len(self.trials)];obs=[x for x in self.observations if self.trial_start<=x['time']<=end]
  events=[e for e in self.events[self.event_start:] if e['source']=='camera'];pred=max(set(x['label'] for x in obs),key=lambda y:sum(x['label']==y for x in obs)) if obs else None
  known=g in self.predictor.classes
  valid=bool(obs) and self.cap is not None
  command_correct=(not events if g=='no_gesture' else len(events)==1 and events[0]['gesture']==g) if known else None
  row={'trial':len(self.trials)+1,'expected':g,'duration_seconds':end-self.trial_start,'valid_capture':valid,'modal_prediction':pred,'classification_correct':pred==g if known and valid else None,'command_correct':command_correct if valid else None,'command_count':len(events),'commands':events,'prediction_count':len(obs),'observations':obs,'ground_truth':'participant instructed; not independently verified'}
  self.trials.append(row);self.armed.set(False);self.gate.reset();self.active=False;self.persist();self.next_button.state(['!disabled'])
  if len(self.trials)==len(self.plan):self.stop_camera()
  self.prompt()
 def redo(self):
  if self.active or not self.trials:return
  self.trials.pop();self.persist();self.prompt()
 def persist(self):
  (OUT/'live_test_results.json').write_text(json.dumps({'protocol':'50 known-gesture trials (10 per class) plus 3 rejection intervals. Participant supplies intended gesture. Four-second attempt windows; trial-level modal class and exactly one correct command, or no command for neutral. No external keyboard control.','complete':len(self.trials)==len(self.plan),'trials':self.trials},indent=2))
  keys=['trial','expected','duration_seconds','valid_capture','modal_prediction','classification_correct','command_correct','command_count','prediction_count']
  with (OUT/'live_test_results.csv').open('w') as f:
   w=csv.DictWriter(f,fieldnames=keys);w.writeheader();w.writerows({k:r[k] for k in keys} for r in self.trials)
 def save_stop(self):
  self.active=False;self.stop_camera();self.persist();self.guide.set('Test stopped. Completed trials saved. Close the window to exit.')
 def close(self):self.persist();super().close()
if __name__=='__main__':
 root=tk.Tk();app=GuidedTest(root);root.mainloop()
