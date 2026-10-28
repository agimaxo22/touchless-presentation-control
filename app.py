"""Local desktop gesture lab. No camera or external key events before user action."""
import argparse
import base64
import json
import queue
import threading
import time
from pathlib import Path
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import cv2
import numpy as np
from controller import GestureGate

ROOT = Path(__file__).resolve().parent

class App:
    def __init__(self, root):
        self.root = root
        self.root.title('Touchless Presentation Control — Local Gesture Lab')
        self.root.geometry('1100x820')
        self.root.minsize(850,650)
        self.predictor = None
        self.jobs = queue.Queue(maxsize=1)
        self.results = queue.Queue()
        self.cap = None
        self.pending = False
        self.closed = False
        self.replay = None
        self.gate = GestureGate()
        self.external = False
        self.keyboard = None
        self.listener = None
        self.external_ready = float('inf')
        self.armed = tk.BooleanVar(value=False)
        self.camera_id = tk.IntVar(value=0)
        self.status = tk.StringVar(value='Loading the trained model…')
        self.info = tk.StringVar(value='Practice mode. Camera is off. External keyboard control is off.')
        self.score_text = tk.StringVar(value='')
        self.slide = -1
        self.pointer = False
        self.events = []
        self.slides = [
            ('Touchless Presentation Control','A university machine-learning project\nCustom CNN vs MobileNetV2 vs augmentation'),
            ('Dataset and evaluation','4,000 HaGRID hand crops\nPeople and source images kept separate across splits\nTwo seeds and six epochs per model'),
            ('Measured test results','CNN: 37.42%\nMobileNetV2: 93.68%\nMobileNetV2 + augmentation: 93.32%\nMeans across two seeds; not webcam accuracy.'),
            ('Lecture connections','Convolution and pooling · ReLU · Softmax\nCross-entropy and backpropagation\nTransfer learning and augmentation'),
            ('Limitations','Keep one hand inside the guide.\nUnknown objects can receive high scores.\nLive-camera performance requires a separate study.')]
        ttk.Label(root,text='Touchless Presentation Control',font=('Helvetica',23,'bold')).pack(anchor='w',padx=20,pady=(15,5))
        ttk.Label(root,textvariable=self.info,wraplength=1030).pack(anchor='w',padx=20)
        tools=ttk.Frame(root);tools.pack(fill='x',padx=20,pady=12)
        ttk.Button(tools,text='Start camera',command=self.start_camera).pack(side='left',padx=3)
        ttk.Button(tools,text='Stop camera',command=self.stop_camera).pack(side='left',padx=3)
        ttk.Label(tools,text='Camera index:').pack(side='left',padx=(12,3))
        ttk.Spinbox(tools,from_=0,to=5,width=3,textvariable=self.camera_id).pack(side='left')
        ttk.Checkbutton(tools,text='Enable gesture commands',variable=self.armed,command=self.reset_gate).pack(side='left',padx=15)
        ttk.Button(tools,text='External slide control…',command=self.enable_external).pack(side='right')
        content=ttk.Frame(root);content.pack(fill='both',expand=True,padx=20)
        left=ttk.Frame(content);left.pack(side='left',fill='both',expand=True,padx=(0,15))
        right=ttk.Frame(content,width=420);right.pack(side='right',fill='both',expand=True)
        self.preview=tk.Label(left,bg='#101e31',fg='white',text='Camera off\nTry a labeled example below.',width=50,height=18)
        self.preview.pack(fill='both',expand=True)
        ttk.Label(left,textvariable=self.status,font=('Helvetica',13,'bold'),wraplength=520).pack(anchor='w',pady=8)
        ttk.Label(left,textvariable=self.score_text,justify='left').pack(anchor='w')
        practice=ttk.Frame(left);practice.pack(fill='x',pady=8)
        self.example=ttk.Combobox(practice,state='readonly',values=['Open palm','Closed fist','Thumbs up','Peace / two fingers','Neutral hand'])
        self.example.current(0);self.example.pack(side='left',fill='x',expand=True)
        ttk.Button(practice,text='Predict',command=self.predict_example).pack(side='left',padx=4)
        ttk.Button(practice,text='Replay hold',command=self.replay_example).pack(side='left')
        ttk.Button(left,text='Upload tightly cropped hand photo',command=self.upload).pack(anchor='w')
        ttk.Label(left,text='Palm → next · Fist → previous · Thumbs up → start\nPeace → toggle pointer in the built-in slides\nNeutral → no command. Scores are uncalibrated.',wraplength=520).pack(anchor='w',pady=10)
        ttk.Label(right,text='Your presentation',font=('Helvetica',17,'bold')).pack(anchor='w')
        self.slide_view=tk.Canvas(right,bg='#172b4c',height=300,highlightthickness=0)
        self.slide_view.pack(fill='both',expand=True,pady=10)
        self.slide_view.bind('<Configure>',lambda e:self.draw_slide())
        nav=ttk.Frame(right);nav.pack(fill='x')
        for text,label in [('Start','like'),('Previous','fist'),('Next','palm'),('Pointer','peace')]:
            ttk.Button(nav,text=text,command=lambda label=label:self.command(label,'manual')).pack(side='left',padx=2)
        ttk.Button(right,text='Edit presentation text…',command=self.edit_slides).pack(anchor='w',pady=10)
        ttk.Label(right,text='Recent commands').pack(anchor='w')
        self.log=tk.Listbox(right,height=6);self.log.pack(fill='x',pady=5)
        ttk.Button(right,text='Save session log',command=self.save_log).pack(anchor='w')
        ttk.Label(root,text='Escape / Stop camera disables gestures. External mode: F9 disarms globally; automatic timeout after 60 seconds.\nCamera frames stay on this Mac. The app does not record video or contact a prediction server.',wraplength=1050).pack(anchor='w',padx=20,pady=12)
        root.bind('<Escape>',lambda e:self.stop_camera())
        root.protocol('WM_DELETE_WINDOW',self.close)
        threading.Thread(target=self.worker,daemon=True).start()
        root.after(50,self.tick)
        self.draw_slide()

    def worker(self):
        try:
            from predictor import Predictor
            p=Predictor();self.results.put(('ready',p))
        except Exception as e:
            self.results.put(('error',str(e)));return
        while True:
            job=self.jobs.get()
            if job is None:return
            rgb,source=job
            try:
                start=time.monotonic();scores=p.predict(rgb)
                self.results.put(('prediction',(scores,source,(time.monotonic()-start)*1000)))
            except Exception as e:self.results.put(('error',str(e)))

    def show_rgb(self,rgb):
        h,w=rgb.shape[:2];scale=min(500/w,320/h)
        small=cv2.resize(rgb,(max(1,int(w*scale)),max(1,int(h*scale))))
        ok,data=cv2.imencode('.png',cv2.cvtColor(small,cv2.COLOR_RGB2BGR))
        if ok:
            self.photo=tk.PhotoImage(data=base64.b64encode(data).decode())
            self.preview.configure(image=self.photo,text='',width=1,height=1)

    def submit(self,rgb,source):
        if self.predictor is None or self.pending:return
        self.pending=True;self.jobs.put((rgb,source))

    def tick(self):
        if self.closed:return
        try:
            while True:
                kind,value=self.results.get_nowait()
                if kind=='ready':
                    self.predictor=value;self.status.set('Ready. Select a labeled example or start camera.')
                elif kind=='error':
                    self.pending=False;self.status.set('Error: '+value);self.armed.set(False)
                elif kind=='stop':self.disable_external()
                elif kind=='prediction':
                    self.pending=False;scores,source,ms=value;k=int(np.argmax(scores))
                    self.status.set(f'{self.predictor.names[k]} · score {scores[k]:.3f} · {ms:.0f} ms · {source}')
                    self.score_text.set('\n'.join(f'{self.predictor.names[i]}: {scores[i]:.3f}' for i in np.argsort(scores)[::-1]))
                    if source in ('camera','replay'):
                        label=self.gate.update(self.predictor.classes[k],float(scores[k]),time.monotonic(),self.predictor.threshold)
                        if label and self.armed.get():self.command(label,source)
                    if source=='replay' and self.replay:
                        self.replay[1]-=1
                        if self.replay[1]>0:self.root.after(300,self.next_replay)
                        else:self.replay=None
        except queue.Empty:pass
        if self.cap is not None:
            ok,frame=self.cap.read()
            if ok:
                h,w=frame.shape[:2];side=int(min(h,w)*.6);x=(w-side)//2;y=(h-side)//2
                crop=cv2.cvtColor(frame[y:y+side,x:x+side],cv2.COLOR_BGR2RGB)
                view=cv2.flip(frame,1);cv2.rectangle(view,(x,y),(x+side,y+side),(255,220,80),2)
                self.show_rgb(cv2.cvtColor(view,cv2.COLOR_BGR2RGB));self.submit(crop,'camera')
            else:self.stop_camera();self.status.set('Camera read failed. Try another camera index.')
        if self.external and time.monotonic()>self.external_ready+60:self.disable_external()
        self.root.after(40,self.tick)

    def start_camera(self):
        if self.predictor is None:return
        self.stop_camera()
        self.cap=cv2.VideoCapture(self.camera_id.get(),cv2.CAP_AVFOUNDATION)
        if not self.cap.isOpened():
            self.stop_camera();messagebox.showerror('Camera unavailable','Allow VS Code or Terminal in macOS System Settings → Privacy & Security → Camera. Then restart the app. Try another camera index if needed.');return
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH,640);self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT,480)
        self.info.set('Camera on. Keep one hand tightly inside the guide. Gesture commands remain off until enabled.')

    def stop_camera(self):
        if self.cap is not None:self.cap.release();self.cap=None
        self.replay=None;self.armed.set(False);self.gate.reset();self.disable_external()
        self.info.set('Camera off. External keyboard control off. Practice mode.')

    def reset_gate(self):self.gate.reset()

    def example_path(self):
        return ROOT/'models'/f'example_{self.predictor.classes[self.example.current()]}.png'

    def read_image(self,path):
        # The same TensorFlow decoder used by the training notebook.
        from predictor import tf
        return tf.io.decode_image(tf.io.read_file(str(path)),channels=3,expand_animations=False).numpy()

    def predict_example(self):
        if self.predictor is None or self.pending:return
        self.stop_camera();rgb=self.read_image(self.example_path());self.show_rgb(rgb);self.submit(rgb,'example')

    def replay_example(self):
        if self.predictor is None or self.pending or self.cap is not None:return
        if self.external:
            messagebox.showinfo('Practice only','Disable external control before replaying test images.');return
        self.gate.reset();rgb=self.read_image(self.example_path());self.show_rgb(rgb);self.replay=[rgb,4];self.next_replay()

    def next_replay(self):
        if self.replay and not self.pending:self.submit(self.replay[0],'replay')

    def upload(self):
        if self.predictor is None or self.pending:return
        path=filedialog.askopenfilename(filetypes=[('Images','*.png *.jpg *.jpeg')])
        if not path:return
        self.stop_camera()
        try:
            rgb=self.read_image(path);h,w=rgb.shape[:2];s=min(h,w);rgb=rgb[(h-s)//2:(h+s)//2,(w-s)//2:(w+s)//2]
            self.show_rgb(rgb);self.submit(rgb,'upload')
        except Exception as e:messagebox.showerror('Image error',str(e))

    def command(self,label,source):
        actions={'palm':'Next slide','fist':'Previous slide','like':'Start / first slide','peace':'Toggle pointer'}
        if label=='like':self.slide=0
        elif self.slide<0:return
        elif label=='palm':self.slide=min(len(self.slides)-1,self.slide+1)
        elif label=='fist':self.slide=max(0,self.slide-1)
        elif label=='peace':self.pointer=not self.pointer
        self.draw_slide()
        event={'time':time.strftime('%Y-%m-%d %H:%M:%S'),'gesture':label,'action':actions[label],'source':source,'external':False}
        if self.external and source=='camera' and time.monotonic()>=self.external_ready:
            from pynput.keyboard import Key
            key={'palm':Key.right,'fist':Key.left,'like':Key.home}.get(label)
            if key:
                try:self.keyboard.press(key);self.keyboard.release(key);event['external']=True
                except Exception as e:self.disable_external();self.status.set('Keyboard control stopped: '+str(e))
        self.events.append(event);self.log.insert(0,f"{time.strftime('%H:%M:%S')} · {actions[label]} · {source}")

    def enable_external(self):
        if self.external:self.disable_external();return
        if self.cap is None:
            messagebox.showinfo('Start camera first','External control requires a live camera. Replay and uploaded images never send external keys.');return
        if not messagebox.askokcancel('Enable external keyboard control?',
            'This will send Right, Left and Home keys to whichever application is focused.\n\nOpen your slideshow first. After enabling, you have five seconds to focus it. F9 stops control globally, or use Stop camera. It expires after 60 seconds.\n\nThe pointer command affects the built-in slides only. macOS Accessibility permission may be required.'):return
        try:
            from pynput.keyboard import Controller,Listener,Key
            if not Listener.IS_TRUSTED:raise PermissionError('Grant Accessibility permission to the app that launches Python (VS Code or Terminal), then restart.')
            self.keyboard=Controller()
            self.listener=Listener(on_press=lambda k:self.results.put(('stop',None)) if k==Key.f9 else None)
            self.listener.start();self.external=True;self.external_ready=time.monotonic()+5;self.armed.set(True);self.gate.reset()
            self.info.set('External control starts in 5 seconds. Focus your slideshow. F9 stops. Automatic timeout: 60 seconds.')
        except Exception as e:messagebox.showerror('External control unavailable',str(e));self.disable_external()

    def disable_external(self):
        self.external=False
        if self.listener is not None:self.listener.stop();self.listener=None
        self.keyboard=None

    def draw_slide(self):
        canvas=self.slide_view;canvas.delete('all');w=max(350,canvas.winfo_width())
        title,body=self.slides[self.slide] if self.slide>=0 else ('Ready when you are','Start the built-in slides or enable gestures and hold thumbs up.')
        canvas.create_text(22,24,anchor='nw',text=f'Slide {self.slide+1} of {len(self.slides)}' if self.slide>=0 else 'Presentation ready',fill='#c9ddff',font=('Helvetica',11))
        canvas.create_text(22,60,anchor='nw',text=title,fill='white',width=w-44,font=('Helvetica',20,'bold'))
        canvas.create_text(22,125,anchor='nw',text=body,fill='white',width=w-44,font=('Helvetica',14))
        if self.pointer:canvas.create_oval(w/2-7,280,w/2+7,294,fill='#fbbf24',outline='white')

    def edit_slides(self):
        win=tk.Toplevel(self.root);win.title('Edit presentation');win.geometry('700x420')
        ttk.Label(win,text='One slide per line: title | body. Use \\n for line breaks.').pack(pady=8)
        editor=tk.Text(win);editor.pack(fill='both',expand=True,padx=10)
        editor.insert('1.0','\n'.join(t+' | '+b.replace('\n','\\n') for t,b in self.slides))
        def save():
            slides=[]
            for line in editor.get('1.0','end').splitlines():
                if line.strip():
                    title,_,body=line.partition('|');slides.append((title.strip(),body.strip().replace('\\n','\n')))
            if slides:self.slides=slides;self.slide=-1;self.draw_slide();win.destroy()
        ttk.Button(win,text='Apply slides',command=save).pack(pady=8)

    def save_log(self):
        path=filedialog.asksaveasfilename(defaultextension='.json',initialfile='gesture_session_log.json')
        if path:Path(path).write_text(json.dumps(self.events,indent=2))

    def close(self):
        self.closed=True;self.stop_camera()
        try:self.jobs.put_nowait(None)
        except queue.Full:pass
        self.root.destroy()

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--verify',action='store_true');parser.add_argument('--image');parser.add_argument('--smoke-test',action='store_true');args=parser.parse_args()
    if args.verify or args.image:
        from predictor import Predictor
        p=Predictor()
        if args.verify:print(json.dumps(p.verify(),indent=2))
        else:
            scores=p.image(args.image);print(json.dumps(dict(zip(p.classes,map(float,scores))),indent=2))
        return
    root=tk.Tk();app=App(root)
    if args.smoke_test:
        deadline=time.monotonic()+40
        def check():
            if app.predictor is not None:
                app.command('like','manual');app.command('palm','manual')
                assert app.slide==1
                app.example.current(0);app.predict_example()
                root.after(1500,finish)
            elif time.monotonic()>deadline:
                print('GUI smoke test failed:',app.status.get(),flush=True);app.close();raise RuntimeError('Model did not load in the GUI')
            else:root.after(200,check)
        def finish():
            assert not app.pending, 'Prediction worker did not finish'
            assert app.cap is None and not app.external
            print('PASS: Tk window, model worker, image prediction, slide navigation, and camera-off default.',flush=True)
            app.close()
        root.after(200,check)
    root.mainloop()

if __name__=='__main__':main()
