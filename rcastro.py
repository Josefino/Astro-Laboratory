import os
import shutil
import subprocess
from pathlib import Path
import numpy as np
import tifffile
from processing import read_fits,read_tiff,write_fits,luminance
from scipy.ndimage import gaussian_filter


def resolve_executable(configured):
    configured=os.path.expandvars(os.path.expanduser(configured))
    found=shutil.which(configured)
    if not found:
        candidate=Path(configured)
        if candidate.is_file() and os.access(candidate,os.X_OK):found=str(candidate)
    return str(Path(found).resolve()) if found else None

def executable():
    return resolve_executable(os.environ.get('RC_ASTRO_PATH','rc-astro'))

def status():
    exe=executable()
    out={'available':bool(exe),'products':{}}
    if exe:
        for product in ['bxt','nxt','sxt']:
            try:
                result=subprocess.run([exe,product,'--license'],capture_output=True,text=True,timeout=20)
                out['products'][product]={'returncode':result.returncode,'message':(result.stdout+result.stderr)[-2500:]}
            except (OSError,subprocess.TimeoutExpired) as e:
                out['products'][product]={'message':str(e)}
    return out

def match_orientation(reference,result):
    """Match only exact pixel permutations; never interpolate or mix misoriented data."""
    if reference.ndim!=result.ndim or (reference.ndim==3 and reference.shape[2]!=result.shape[2]):
        raise ValueError('RC-Astro changed the channel count; output rejected.')
    stride=max(1,int(np.ceil(max(reference.shape[:2])/384)))
    def bands(image):
        thumbnail=luminance(image[::stride,::stride])
        return [gaussian_filter(thumbnail,lo)-gaussian_filter(thumbnail,hi) for lo,hi in ((1,8),(4,24))]
    ref_bands=bands(reference)
    def correlation(x,y):
        x=x-x.mean();y=y-y.mean()
        norm=np.linalg.norm(x)*np.linalg.norm(y)
        return float(np.sum(x*y)/norm) if norm>1e-20 else -1.0
    candidates=[]
    for turns in range(4):
        rotated=np.rot90(result,turns,axes=(0,1))
        for mirror in (False,True):
            candidate=np.flip(rotated,axis=1) if mirror else rotated
            if candidate.shape!=reference.shape:continue
            scores=[correlation(x,y) for x,y in zip(ref_bands,bands(candidate))]
            score=0.85*scores[0]+0.15*scores[1]
            name=f'rotate_{turns*90}' + ('_mirror_x' if mirror else '')
            candidates.append((score,name,candidate))
    if not candidates:
        raise ValueError('RC-Astro changed the image dimensions; output rejected.')
    candidates.sort(key=lambda item:item[0],reverse=True)
    best,name,image=candidates[0]
    runner=candidates[1][0] if len(candidates)>1 else -1
    if best<0.3 or best-runner<0.08:
        raise ValueError('RC-Astro output orientation could not be verified reliably. The result was not blended with the original. Use an image with identifiable structure, or provide input and output FITS images for diagnosis.')
    diagnostic={'transform':name,'correlation':best,'runner_up_correlation':runner}
    return image,diagnostic

def run(product,a,header,directory,options=()):
    exe=executable()
    if not exe:
        raise ValueError('RC-Astro CLI not found. Enter and save the CLI path in the RC-Astro section.')
    low=float(a.min()); span=max(float(a.max())-low,1e-12)
    normalized=(a-low)/span
    if product=='sxt':
        source=directory/'rc-sxt-input.tif'
        target=directory/'rc-sxt-output.tif'
        tifffile.imwrite(source,normalized.astype(np.float32),photometric='rgb' if a.ndim==3 else 'minisblack',
                         extratags=[(274,'H',1,1,False)])
    else:
        source=directory/f'rc-{product}-input.fits'
        target=directory/f'rc-{product}-output.fits'
        write_fits(normalized,header,source)
    target.unlink(missing_ok=True)
    args=[exe,product,str(source),'--output',str(target),'--depth','32F',*options]
    try:
        result=subprocess.run(args,capture_output=True,text=True,timeout=1800)
    except subprocess.TimeoutExpired:
        raise ValueError(f'RC-Astro {product} exceeded the 30-minute time limit.')
    (directory/f'rc-{product}.log').write_text(result.stdout+'\n'+result.stderr,encoding='utf-8')
    if result.returncode or not target.is_file():
        raise ValueError(f'RC-Astro {product} failed. Check the license/model using rc-astro {product}. The log is in the job folder.')
    if product=='sxt':
        b,orientation=read_sxt_tiff(target)
        if b.shape!=a.shape:
            raise ValueError('StarXTerminator changed image dimensions or channel count; output rejected.')
    else:
        b,_=read_fits(target)
        b,orientation=match_orientation(normalized,b)
    import json
    (directory/f'rc-{product}-orientation.json').write_text(json.dumps(orientation,indent=2),encoding='utf-8')
    with (directory/f'rc-{product}.log').open('a',encoding='utf-8') as log:
        log.write('\nOrientation handling: '+json.dumps(orientation)+'\n')
    return b*span+low


def read_sxt_tiff(path):
    """TIFF uses explicit display orientation, independent of disappearing stars."""
    with tifffile.TiffFile(path) as image:
        orientations={int(page.tags['Orientation'].value) if 'Orientation' in page.tags else 1 for page in image.pages}
    if len(orientations)!=1:raise ValueError('SXT TIFF contains inconsistent plane orientations.')
    tag=orientations.pop()
    b,_=read_tiff(path)
    if tag==2:b=np.flip(b,axis=1)
    elif tag==3:b=np.rot90(b,2,axes=(0,1))
    elif tag==4:b=np.flip(b,axis=0)
    elif tag==5:b=np.swapaxes(b,0,1)
    elif tag==6:b=np.rot90(b,-1,axes=(0,1))
    elif tag==7:b=np.flip(np.swapaxes(b,0,1),axis=(0,1))
    elif tag==8:b=np.rot90(b,1,axes=(0,1))
    elif tag!=1:raise ValueError('Unknown TIFF orientation from RC-Astro.')
    return b,{'method':'TIFF orientation metadata; no star-based registration','tiff_orientation':tag}
