"""Packaged desktop entry: loopback server plus browser, with an authenticated Quit action."""
import ctypes
import json
import logging
import os
from pathlib import Path
import subprocess
import sys
import threading
import urllib.request
import webbrowser


def user_directory():
    if sys.platform=='darwin':return Path.home()/'Library/Application Support/AstroProcessor'
    if sys.platform=='win32':return Path(os.environ.get('LOCALAPPDATA',str(Path.home()/'AppData/Local')))/'AstroProcessor'
    return Path.home()/'.local/share/AstroProcessor'


def show_error(message):
    logging.error(message)
    if sys.platform=='win32':ctypes.windll.user32.MessageBoxW(None,message,'Astro Laboratory',0x10)
    elif sys.platform=='darwin':
        text=json.dumps(message)
        subprocess.run(['osascript','-e',f'display dialog {text} with title "Astro Laboratory" buttons {{"OK"}} default button "OK"'],check=False)
    else:print(message,file=sys.stderr)


def existing_instance():
    try:
        with urllib.request.urlopen('http://127.0.0.1:8765/api/config',timeout=2) as response:
            return json.load(response).get('app_id')=='astro-processor'
    except Exception:return False


def main():
    directory=user_directory();directory.mkdir(parents=True,exist_ok=True)
    config_file=directory/'desktop.json'
    if config_file.is_file():
        try:
            config=json.loads(config_file.read_text(encoding='utf-8'))
            for key,variable in [('rc_astro_path','RC_ASTRO_PATH'),('graxpert_path','GRAXPERT_PATH'),('work_directory','ASTRO_WORKDIR')]:
                if isinstance(config.get(key),str) and config[key]:os.environ[variable]=config[key]
        except (OSError,ValueError,AttributeError) as exc:
            show_error(f'Invalid desktop configuration: {config_file}\n{exc}')
            return 1
    log=directory/'desktop.log'
    logging.basicConfig(filename=log,level=logging.INFO,format='%(asctime)s %(levelname)s %(message)s')
    # Console-less PyInstaller apps may have no stdout/stderr. Keep diagnostics locally.
    if sys.stdout is None:sys.stdout=log.open('a',encoding='utf-8',buffering=1)
    if sys.stderr is None:sys.stderr=sys.stdout
    if existing_instance():
        webbrowser.open('http://127.0.0.1:8765');return
    try:
        from werkzeug.serving import make_server
        from app import app,POOL
        app.config['DESKTOP_MODE']=True
        server=make_server('127.0.0.1',8765,app,threaded=True)
        app.config['SHUTDOWN_SERVER']=server.shutdown
        # The socket is bound before the browser is opened.
        timer=threading.Timer(0.5,webbrowser.open,args=('http://127.0.0.1:8765',));timer.daemon=True;timer.start()
        try:server.serve_forever()
        finally:
            server.server_close();POOL.shutdown(wait=True)
    except BaseException as exc:
        if isinstance(exc,KeyboardInterrupt):return
        logging.exception('Desktop launch failed')
        show_error(f'Could not start Astro Laboratory. Port 8765 may already be in use.\n\nDetails: {exc}\n\nLog: {log}')
        sys.exit(1)


if __name__=='__main__':sys.exit(main() or 0)
