"""Run installed GraXpert AI background extraction on linear float FITS."""
import os
import json
import shutil
import subprocess
from pathlib import Path
import numpy as np
from processing import read_fits,write_fits


def executable(configured=''):
    candidates=[configured] if configured else [os.environ.get('GRAXPERT_PATH',''),'/Applications/GraXpert.app','GraXpert','graxpert']
    for candidate in candidates:
        if not candidate:continue
        path=Path(candidate).expanduser()
        if path.suffix.lower()=='.app':path=path/'Contents/MacOS/GraXpert'
        found=shutil.which(str(path))
        if found:return found
        if path.is_file() and os.access(path,os.X_OK):return str(path.resolve())
    return None


def run(a,header,directory,configured='',smoothing=0.5,gpu=True,mode='ai',points=None,sample_size=25,save_background=False):
    exe=executable(configured)
    if not exe:raise ValueError('GraXpert not found. Enter the application (.app) or executable path.')
    directory=Path(directory)
    low=float(a.min());span=max(float(a.max())-low,1e-12)
    source=directory/'graxpert_input.fits'
    base=directory/'graxpert_corrected'
    write_fits((a-low)/span,header,source)
    args=[exe,str(source),'-cli','-cmd','background-extraction','-correction','Subtraction',
          '-smoothing',str(smoothing),'-gpu','true' if gpu else 'false','-output',str(base)]
    if mode=='rbf':
        pixel_points=validate_points(points or [],a.shape,sample_size)
        preferences={'interpol_type_option':'RBF','background_points':pixel_points,
                     'sample_size':sample_size,'RBF_kernel':'thin_plate','smoothing_option':smoothing,
                     'corr_type':'Subtraction','saveas_stretched':False,'ai_gpu_acceleration':gpu}
        preferences_file=directory/'graxpert_points.json'
        preferences_file.write_text(json.dumps(preferences,indent=2),encoding='utf-8')
        args.extend(['-preferences_file',str(preferences_file)])
    if save_background:args.append('-bg')
    logfile=directory/'graxpert.log'
    try:
        with logfile.open('w',encoding='utf-8') as log:
            completed=subprocess.run(args,stdout=log,stderr=subprocess.STDOUT,text=True,timeout=1800)
    except subprocess.TimeoutExpired:
        raise ValueError('GraXpert exceeded the 30-minute time limit. Check the model and graxpert.log.')
    targets=[base.with_suffix(ext) for ext in ('.fits','.fit','.fts')]
    target=next((f for f in targets if f.is_file()),None)
    if completed.returncode or target is None:
        raise ValueError('GraXpert failed or did not produce a FITS image. Test background extraction directly in GraXpert. See graxpert.log in the job folder.')
    corrected,_=read_fits(target)
    if corrected.shape!=a.shape:raise ValueError('GraXpert changed the image dimensions; output rejected.')
    if save_background:
        model_path=directory/'graxpert_corrected_background.fits'
        if not model_path.is_file():raise ValueError('GraXpert did not save the background model. For manual samples, check that your installed version supports -preferences_file and -bg.')
        model,_=read_fits(model_path)
        if model.shape!=a.shape:raise ValueError('GraXpert background model dimensions do not match.')
        write_fits(model*span+low,header,directory/'graxpert_background_model.fits',history=['GraXpert background model, restored to input units.'])
    return corrected*span+low


def validate_points(points,shape,sample_size):
    h,w=shape[:2];half=sample_size//2
    converted=[]
    for x,y in points:
        px,py=int(round(x*(w-1))),int(round(y*(h-1)))
        if px<half or py<half or px>=w-half or py>=h-half:
            raise ValueError('A background sample extends beyond the image edge. Move it inward or reduce the sample size.')
        if [px,py] not in converted:converted.append([px,py])
    if len(converted)<6:raise ValueError('For RBF, select at least 6 distinct samples of true background.')
    design=np.column_stack([np.array(converted),np.ones(len(converted))])
    if np.linalg.matrix_rank(design)<3:raise ValueError('Sample points are collinear. Distribute them around the object.')
    return converted
