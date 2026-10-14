import io
import json
import os
import secrets
import sys
import threading
import traceback
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
import numpy as np
from flask import Flask,request,jsonify,send_file,abort
from werkzeug.exceptions import HTTPException
from processing import unscreen_layer,rendered_color,render_separate_layers,read_fits,read_tiff,analyze,settings,process,display_params,stretch,png,write_fits,file_hash,luminance,reduce_green_display,apply_s_curve,measure_sample_noise
import tifffile
import rcastro
import graxpert_adapter

BASE=Path(__file__).resolve().parent
if getattr(sys,'frozen',False):
    if sys.platform=='darwin':
        default_data=Path.home()/'Library/Application Support/AstroProcessor/work'
    elif sys.platform=='win32':
        default_data=Path(os.environ.get('LOCALAPPDATA',str(Path.home()/'AppData/Local')))/'AstroProcessor/work'
    else:
        default_data=Path.home()/'.local/share/AstroProcessor/work'
else:
    default_data=BASE/'work'
DATA=Path(os.environ.get('ASTRO_WORKDIR',str(default_data))).expanduser().resolve()
DATA.mkdir(parents=True,exist_ok=True)
RUNTIME_SETTINGS=DATA/'application-settings.json'
if RUNTIME_SETTINGS.is_file():
    try:
        saved=json.loads(RUNTIME_SETTINGS.read_text(encoding='utf-8'))
        if isinstance(saved.get('rc_astro_path'),str):os.environ['RC_ASTRO_PATH']=saved['rc_astro_path']
    except (OSError,ValueError,TypeError):pass
app=Flask(__name__,static_folder='static')
app.config['MAX_CONTENT_LENGTH']=512*1024*1024
TOKEN=secrets.token_urlsafe(32)
POOL=ThreadPoolExecutor(max_workers=1)
JOBS={}; LOCK=threading.Lock()

@app.before_request
def local_only():
    if request.host.split(':')[0] not in ('127.0.0.1','localhost'):
        abort(403)
    if request.method=='POST' and request.headers.get('X-Astro-Token')!=TOKEN:
        abort(403)

@app.errorhandler(Exception)
def error(e):
    if isinstance(e,HTTPException): return jsonify(error=e.description),e.code
    if isinstance(e,(ValueError,KeyError,TypeError)): return jsonify(error=str(e)),400
    traceback.print_exc()
    return jsonify(error='Internal error. See the terminal for details.'),500

@app.get('/')
def index():
    return send_file(BASE/'static/index.html')

@app.get('/api/config')
def config():
    return jsonify(token=TOKEN,app_id='astro-processor',desktop=bool(app.config.get('DESKTOP_MODE')),
                   rc_available=bool(rcastro.executable()),rc_astro_path=os.environ.get('RC_ASTRO_PATH',''),graxpert_path=graxpert_adapter.executable() or '',version='0.9.0')

@app.post('/api/quit')
def quit_desktop():
    callback=app.config.get('SHUTDOWN_SERVER')
    if not callback:abort(404)
    with LOCK:
        if any(job.get('status') in ('queued','running') for job in JOBS.values()):
            return jsonify(error='Wait for image processing to finish before quitting.'),409
    threading.Thread(target=callback,daemon=True).start()
    return jsonify(status='stopping')

@app.post('/api/rc-path')
def save_rc_path():
    payload=request.get_json() or {}
    value=payload.get('path','')
    if not isinstance(value,str):raise ValueError('Enter the path to the RC-Astro CLI executable.')
    value=value.strip().strip('"').strip("'")
    resolved=rcastro.resolve_executable(value or 'rc-astro')
    if not resolved:
        raise ValueError('CLI executable not found or not executable. Select the RC-Astro CLI file, not a license, plugin or folder.')
    with LOCK:
        if any(job.get('status') in ('queued','running') for job in JOBS.values()):
            return jsonify(error='Wait for processing to finish before changing the CLI path.'),409
        saved=json.loads(RUNTIME_SETTINGS.read_text(encoding='utf-8')) if RUNTIME_SETTINGS.is_file() else {}
        saved['rc_astro_path']=resolved
        temporary=RUNTIME_SETTINGS.with_suffix('.tmp')
        temporary.write_text(json.dumps(saved,indent=2),encoding='utf-8')
        temporary.replace(RUNTIME_SETTINGS)
        os.environ['RC_ASTRO_PATH']=resolved
    return jsonify(available=True,path=resolved,message='CLI path verified and saved. You can now check licenses.')

@app.get('/api/rc-status')
def rc_status(): return jsonify(rcastro.status())


def session(sid):
    if len(sid)!=32 or any(c not in '0123456789abcdef' for c in sid): abort(404)
    directory=DATA/sid
    if not (directory/'input.fits').is_file(): abort(404)
    return directory

@app.post('/api/upload')
def upload():
    f=request.files.get('file')
    if not f or Path(f.filename or '').suffix.lower() not in ('.fits','.fit','.fts','.tif','.tiff'):
        raise ValueError('Input must be a linear FITS or 16/32/64-bit TIFF image.')
    sid=secrets.token_hex(16); directory=DATA/sid; directory.mkdir()
    original_name='original'+Path(f.filename).suffix.lower()
    original=directory/original_name
    f.save(original)
    try:
        a,h=read_tiff(original) if original.suffix in ('.tif','.tiff') else read_fits(original,allow_bayer=True,allow_nonlinear=True)
        write_fits(a,h,directory/'input.fits')
        metrics=analyze(a,h); scale=display_params(a)
        png(stretch(a,scale,30),directory/'input.png')
        metadata={'filename':Path(f.filename).name,'original_name':original_name,'sha256':file_hash(original),'metrics':metrics,'scale':scale}
        (directory/'input.json').write_text(json.dumps(metadata,ensure_ascii=False,indent=2),encoding='utf-8')
    except Exception:
        import shutil; shutil.rmtree(directory); raise
    return jsonify(id=sid,**metadata,preview=f'/api/file/{sid}/input.png')

@app.post('/api/sample-noise/<sid>')
def sample_noise(sid):
    directory=session(sid)
    p=settings(request.get_json() or {})
    a,_=read_fits(directory/'input.fits',allow_nonlinear=True)
    return jsonify(measure_sample_noise(a,p['background_points'],p['graxpert_sample_size']))

@app.post('/api/background/<sid>')
@app.post('/api/process/<sid>')
def start(sid):
    directory=session(sid)
    p=settings(request.get_json() or {})
    preview=request.path.startswith('/api/background/')
    if preview:
        p['gradient']=True
        p['gradient_method']='graxpert'
        p['_background_preview']=True
    if not preview and any(p[k] for k in ('bxt','nxt','sxt')) and not rcastro.executable():
        raise ValueError('RC-Astro CLI is unavailable. Disable RC tools or install the CLI.')
    if p['gradient'] and p['gradient_method']=='graxpert' and (p['strength'] or preview) and not graxpert_adapter.executable(p['graxpert_path']):
        raise ValueError('GraXpert was not found at the specified path.')
    if p['gradient'] and p['gradient_method']=='graxpert' and p['graxpert_mode']=='rbf':
        meta=json.loads((directory/'input.json').read_text(encoding='utf-8'))
        graxpert_adapter.validate_points(p['background_points'],meta['metrics']['shape'],p['graxpert_sample_size'])
    job=secrets.token_hex(16); destination=directory/job; destination.mkdir()
    with LOCK: JOBS[job]={'status':'queued','progress':'Queued.'}
    POOL.submit(work,sid,job,destination,p)
    return jsonify(job=job)


def work(sid,job,directory,p):
    def update(**kw):
        with LOCK:
            state=JOBS[job]
            state.update(kw)
            message=kw.get('progress')
            if message:
                history=state.setdefault('history',[])
                if not history or history[-1]!=message:
                    history.append(message)
                    print(f'[Astro {job[:8]}] {message}',flush=True)
    try:
        update(status='running',progress='Processing linear data…')
        source=DATA/sid
        a,h=read_fits(source/'input.fits',allow_nonlinear=True)
        nonlinear=p['already_stretched']
        if h.get('APLINEAR') is False and not nonlinear:raise ValueError('FITS is marked nonlinear. Enable Already stretched input.')
        if p['unscreen_stars'] and not nonlinear:raise ValueError('Unscreen Stars requires Already stretched input mode.')
        if nonlinear:
            if a.min()<0 or a.max()>p['input_white']*1.00001:raise ValueError('Input values exceed the selected input white level. Choose the correct scale.')
            a=a/p['input_white'];h=h.copy();h['APLINEAR']=False
            p=p.copy();p['bxt']=False;p['gradient']=False
        sample_noise_report=measure_sample_noise(a,p['background_points'],p['graxpert_sample_size']) if p['background_points'] else None
        factor=p['strength']/100
        working=a
        log=[]
        if nonlinear:log.append("Already stretched: input divided by selected white level; no black-point subtraction or percentile normalization. BlurXTerminator and gradient removal skipped; additional stretch bypassed.")
        base_settings=p.copy()
        if p['gradient'] and p['gradient_method']=='graxpert':
            base_settings['gradient']=False
            if factor or p.get('_background_preview'):
                update(progress='GraXpert: '+('RBF using background samples…' if p['graxpert_mode']=='rbf' else 'AI background extraction…'))
                corrected=graxpert_adapter.run(a,h,directory,p['graxpert_path'],p['graxpert_smoothing'],p['graxpert_gpu'],p['graxpert_mode'],p['background_points'],p['graxpert_sample_size'],True)
                working=a+factor*(corrected-a)
                model_file=directory/'graxpert_background_model.fits'
                if model_file.is_file():
                    background_model,_=read_fits(model_file)
                    png(stretch(background_model,display_params(background_model),15),directory/'background.png')
                write_fits(a-corrected,h,directory/'graxpert_removed_background.fits',history=['Input minus GraXpert subtraction result; not scaled by overall strength.'])
                log.append('GraXpert '+p['graxpert_mode']+': Subtraction on linear FITS; blend amount follows overall processing strength.')
        if p.get('_background_preview'):
            scale=json.loads((source/'input.json').read_text(encoding='utf-8'))['scale']
            model,_=read_fits(directory/'graxpert_background_model.fits')
            png(stretch(model,display_params(model),15),directory/'background.png')
            png(stretch(a,scale,p['stretch'],p['saturation']),directory/'before.png')
            png(stretch(working,scale,p['stretch'],p['saturation']),directory/'after.png')
            delta=working-a
            noise=max(analyze(a,h)['noise_estimate'],1e-12)
            png(np.clip(0.5+luminance(delta)/(6*noise),0,1),directory/'difference.png')
            png(np.clip(np.abs(luminance(delta))/(3*noise),0,1),directory/'changes.png')
            write_fits(working,h,directory/'gradient_preview_linear.fits')
            report={'kind':'background_preview','settings':p,'steps':log,'note':'Model uses its own display scale, not shared with before/after. Other processing tools have not run.'}
            (directory/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
            files=['graxpert_background_model.fits','graxpert_removed_background.fits','gradient_preview_linear.fits','report.json']
            update(status='done',progress='Background model preview ready; no other processing tools were run.',result={'prefix':f'/api/result/{sid}/{job}/','files':files,'report':report,'kind':'background_preview'})
            return
        if not p['gradient']:
            update(progress='Gradient removal disabled: GraXpert is not running.')
        elif p['gradient_method']!='graxpert':
            update(progress='Gradient: basic plane model; GraXpert is not selected.')
        elif not factor:
            update(progress='GraXpert skipped: overall strength is 0%.')
        else:
            update(progress='GraXpert complete. Continuing linear processing…')
        gradient_settings=base_settings.copy();gradient_settings.update(denoise=0,detail=0)
        b,base_log=process(working,gradient_settings)
        base_settings['gradient']=False
        log.extend(base_log)
        if p['bxt'] and factor:
            update(progress='BlurXTerminator…')
            corrected=rcastro.run('bxt',b,h,directory, ['--sharpen-stars',str(p['star_sharpen']),
              '--adjust-star-halos',str(p['halo']),'--sharpen-nonstellar',str(p['detail']/100)])
            b=corrected; log.append('BlurXTerminator on linear data; native sharpening and halo parameters used without additional blending.')
        stars=None
        if p['sxt'] and factor:
            update(progress='StarXTerminator…')
            starless=rcastro.run('sxt',b,h,directory)
            stars=unscreen_layer(b,starless) if p['unscreen_stars'] else b-starless
            b=starless
            write_fits(stars,h,directory/('stars_unscreen.fits' if p['unscreen_stars'] else ('stars_nonlinear.fits' if nonlinear else 'stars_linear.fits')),nonlinear=nonlinear)
            write_fits(starless,h,directory/('starless_nonlinear.fits' if nonlinear else 'starless_linear.fits'),nonlinear=nonlinear)
            log.append('Unscreen extracted immediately from the unmodified SXT input/output pair, before NoiseXTerminator and curves.' if p['unscreen_stars'] else 'StarXTerminator: stars extracted by subtraction before subsequent adjustments.')
        if p['nxt'] and factor and p['denoise']:
            update(progress='NoiseXTerminator…')
            target=b
            clean=rcastro.run('nxt',target,h,directory)
            mixed=target+factor*(p['denoise']/100)*(clean-target)
            b=mixed
            log.append('NoiseXTerminator: default CLI parameters; amount controlled by blending in linear space.')
        b,linear_log=process(b,base_settings)
        log.extend(linear_log)
        starless_processed=b if stars is not None else None
        if stars is not None:
            weighted=stars*(p['star_brightness']/100)
            b=1-(1-b)*(1-weighted) if p['unscreen_stars'] else b+weighted
            log.append(f'SXT: data-layer recombination at {p["star_brightness"]:g} percent brightness; Screen when Unscreen is enabled.')
        update(progress='Preparing previews and exports…')
        scale=json.loads((source/'input.json').read_text(encoding='utf-8'))['scale']
        before=np.clip(a,0,1) if nonlinear else stretch(a,scale,p['stretch'],p['saturation'])
        if stars is not None:
            update(progress='Stretching starless and stars independently…')
            display,object_display,stars_display=render_separate_layers(starless_processed,stars,scale,p)
            png(object_display,directory/'starless_stretched.png',maxsize=max(b.shape[:2]))
            png(stars_display,directory/'stars_stretched.png',maxsize=max(b.shape[:2]))
            if p.get('unscreen_stars'):log.append('Unscreen Stars: inverse Screen extraction before adjustments; Screen recombination after star brightness scaling.')
            log.append('Independent layer rendering; already-stretched mode bypasses stretch. Brightness applied before merging; Screen for Unscreen, addition otherwise. No curve after merging.')
        else:
            display=rendered_color(b,p['saturation']) if nonlinear else stretch(b,scale,p['stretch'],p['saturation'])
            display=apply_s_curve(display,p['s_curve_strength'],p['s_curve_pivot'])
            display=reduce_green_display(display,p['green_reduction'])
        png(before,directory/'before.png'); png(display,directory/'after.png')
        delta=b-a
        noise=max(analyze(a,h)['noise_estimate'],1e-12)
        changed=np.abs(luminance(delta))/(3*noise)
        png(np.clip(changed,0,1),directory/'changes.png')
        png(np.clip(0.5+luminance(delta)/(6*noise),0,1),directory/'difference.png')
        history=['Astro Laboratory 0.9.0',json.dumps(p,sort_keys=True),*log]
        write_fits(b,h,directory/('processed_nonlinear.fits' if nonlinear else 'processed_linear.fits'),nonlinear=nonlinear,history=history)
        write_fits(display,h,directory/'processed_stretched.fits',nonlinear=True,history=history)
        write_fits(delta,h,directory/('difference_nonlinear.fits' if nonlinear else 'difference_linear.fits'),nonlinear=nonlinear,history=['Signed difference: processed minus input'])
        tifffile.imwrite(directory/'processed_16bit.tif',np.round(display*65535).astype('uint16'),photometric='rgb' if b.ndim==3 else 'minisblack')
        png(display,directory/'processed.png',maxsize=max(b.shape[:2]))
        report={'sample_noise':sample_noise_report,'version':'0.9.0','background_model_available':(directory/'background.png').is_file(),'input_sha256':json.loads((source/'input.json').read_text(encoding='utf-8'))['sha256'],'settings':p,
            'before':analyze(a,h),'after':analyze(b,h),'steps':log,
            'changed_above_3_noise_fraction':float(np.mean(changed>1)),
            'clipped_display_fraction':float(np.mean((display<=0)|(display>=1))),
            'integrity':'No generative fill. Change maps measure modifications, not evidence reliability. One stack cannot certify details. RC-Astro uses learned models; inspect artifacts.',
            'color_calibration':'Not performed. Saturation is aesthetic; not photometric calibration.'}
        if nonlinear:
            for label in ('before','after'):report[label]['linearity']='User-declared already stretched input; normalized by selected input white level.'
        (directory/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
        files=[f.name for f in directory.iterdir() if f.name in ['starless_stretched.png','stars_stretched.png','processed_linear.fits','processed_stretched.fits','processed_16bit.tif','processed.png','report.json','difference_linear.fits','stars_unscreen.fits','stars_nonlinear.fits','starless_nonlinear.fits','processed_nonlinear.fits','difference_nonlinear.fits','stars_linear.fits','starless_linear.fits','graxpert_removed_background.fits','graxpert_background_model.fits']]
        update(status='done',progress='Done.',result={'prefix':f'/api/result/{sid}/{job}/','files':sorted(files),'report':report})
    except Exception as e:
        traceback.print_exc(); update(status='error',error=str(e))

@app.get('/api/job/<job>')
def job_status(job):
    with LOCK:
        if job not in JOBS: abort(404)
        return jsonify(JOBS[job])

@app.get('/api/file/<sid>/<name>')
def get_input(sid,name):
    if name not in ('input.png','original.fits'): abort(404)
    directory=session(sid)
    if name=='original.fits':
        name=json.loads((directory/'input.json').read_text(encoding='utf-8'))['original_name']
    return send_file(directory/name,as_attachment=name!='input.png')

@app.get('/api/result/<sid>/<job>/<name>')
def result(sid,job,name):
    directory=session(sid)
    if len(job)!=32 or any(c not in '0123456789abcdef' for c in job): abort(404)
    allowed={'before.png','after.png','changes.png','difference.png','starless_stretched.png','stars_stretched.png','processed_linear.fits','processed_stretched.fits','processed_16bit.tif','processed.png','report.json','difference_linear.fits','stars_unscreen.fits','stars_nonlinear.fits','starless_nonlinear.fits','processed_nonlinear.fits','difference_nonlinear.fits','stars_linear.fits','starless_linear.fits','graxpert_removed_background.fits','graxpert_background_model.fits','gradient_preview_linear.fits','background.png'}
    if name not in allowed: abort(404)
    file=directory/job/name
    if not file.is_file(): abort(404)
    return send_file(file,as_attachment=name not in ('before.png','after.png','changes.png','difference.png','background.png'))

if __name__=='__main__':
    print('Astro Laboratory: http://127.0.0.1:8765')
    app.run(host='127.0.0.1',port=8765,debug=False,threaded=True)
