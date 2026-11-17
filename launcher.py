"""Small desktop launcher; server windows stay hidden."""
from pathlib import Path
import json
import subprocess
import sys
import time
import tkinter as tk
from tkinter import filedialog, messagebox
import urllib.request
import webbrowser
from datetime import datetime

ROOT=Path(__file__).resolve().parent

def launch(port=8768,folder='data',demo=False):
    url=f'http://127.0.0.1:{port}'
    try:
        with urllib.request.urlopen(url+'/api/state',timeout=1) as r:info=json.load(r)
        if 'properties' not in info or 'leases' not in info:raise ValueError('Another application is using this port.')
    except (OSError,ValueError):
        log=(ROOT/f'launcher-{port}.log').open('a')
        args=[sys.executable,str(ROOT/'server.py'),'--port',str(port),'--data-dir',str(ROOT/folder)]
        if demo:args.append('--demo')
        subprocess.Popen(args,cwd=ROOT,stdout=log,stderr=log,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
        log.close()
        for _ in range(50):
            time.sleep(.1)
            try:
                with urllib.request.urlopen(url+'/api/state',timeout=.5) as r:info=json.load(r)
                if 'properties' in info:break
            except OSError:continue
        else:raise RuntimeError('Hearth could not start. Check the launcher log in this folder.')
    webbrowser.open(url)

def main():
    win=tk.Tk();win.title('Hearth tools');win.geometry('480x300');win.configure(bg='#f5f7ef');win.resizable(False,False)
    tk.Label(win,text='hearth',font=('Georgia',32),bg='#f5f7ef',fg='#24493b').pack(pady=(25,8))
    tk.Label(win,text='Your property workspace',font=('Arial',12),bg='#f5f7ef',fg='#687360').pack(pady=(0,22))
    def open_real():
        try:launch()
        except Exception as e:messagebox.showerror('Unable to open Hearth',str(e))
    def recover():
        source=filedialog.askopenfilename(title='Choose Hearth backup',filetypes=[('Hearth ZIP backup','*.zip')])
        if not source:return
        target=ROOT/('restored-'+datetime.now().strftime('%Y%m%d-%H%M%S'))
        try:
            from restore_backup import restore
            restore(source,target)
            messagebox.showinfo('Backup restored',f'Restored to a separate workspace. Existing data is unchanged.\n\n{target}')
            launch(8767,str(target))
        except Exception as e:messagebox.showerror('Unable to restore',str(e))
    actions=[('Open my workspace',open_real),('Restore a backup to a separate workspace',recover)]
    for text,callback in actions:
        tk.Button(win,text=text,command=callback,font=('Arial',11),bg='#24493b',fg='white',activebackground='#3e634d',activeforeground='white',relief='flat',width=43,pady=10).pack(pady=5)
    tk.Label(win,text='Local data · No subscription',font=('Arial',10),bg='#f5f7ef',fg='#839078').pack(pady=13)
    win.mainloop()
if __name__=='__main__':main()
