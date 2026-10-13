"""Conservative processing. Original physical values are retained in linear export."""
import hashlib
import json
import math
import unicodedata
from pathlib import Path
import numpy as np
from astropy.io import fits
from scipy.ndimage import gaussian_filter, convolve
from PIL import Image
import tifffile

MAX_SAMPLES = 120_000_000

def read_fits(path, allow_bayer=False):
    with fits.open(path, memmap=False) as hdus:
        candidates = [h for h in hdus if isinstance(h, (fits.PrimaryHDU, fits.ImageHDU, fits.CompImageHDU)) and h.header.get('NAXIS', 0) in (2, 3)]
        if not candidates:
            raise ValueError('FITS contains no 2D or RGB image.')
        h = candidates[0]
        shape = tuple(h.header.get(f'NAXIS{i}', 0) for i in range(1, h.header['NAXIS'] + 1))
        if math.prod(shape) > MAX_SAMPLES:
            raise ValueError('Image exceeds the limit of 120 million samples.')
        a = np.array(h.data, dtype=np.float64)
        header = h.header.copy()
    if header.get('APLINEAR') is False:
        raise ValueError('FITS is marked as nonlinear. Load a linear stack.')
    if a.ndim == 3:
        if a.shape[0] == 3:
            a = np.moveaxis(a, 0, -1)
        else:
            raise ValueError('RGB FITS must have three planes in NAXIS3. Data cubes are not supported.')
    if min(a.shape[:2]) < 16:
        raise ValueError('Image must be at least 16 × 16 pixels.')
    if not np.isfinite(a).all():
        raise ValueError('FITS contains NaN/Inf. Correct invalid pixels before importing; they are not replaced synthetically.')
    if a.ndim == 2 and header.get('BAYERPAT') and not allow_bayer:
        raise ValueError('Bayer FITS: explicitly enable debayering during import.')
    if a.ndim == 2 and header.get('BAYERPAT'):
        pattern = str(header['BAYERPAT']).strip().upper()
        if pattern not in ('RGGB', 'BGGR', 'GRBG', 'GBRG'):
            raise ValueError('Unknown Bayer pattern.')
        xo, yo = int(header.get('XBAYROFF', 0)) % 2, int(header.get('YBAYROFF', 0)) % 2
        kernel = np.array([[1,2,1],[2,4,2],[1,2,1]], dtype=float)
        channels=[]
        for color in 'RGB':
            mask=np.zeros_like(a)
            for y in range(2):
                for x in range(2):
                    if pattern[((y+yo)%2)*2+(x+xo)%2] == color:
                        mask[y::2,x::2]=1
            channels.append(convolve(a*mask,kernel,mode='mirror') / convolve(mask,kernel,mode='mirror'))
        a=np.stack(channels,axis=-1)
        header.add_history('Bilinear debayer performed by Astro AI Processor')
        del header['BAYERPAT']
    if a.ndim == 3 and header.get('BAYERPAT'):
        header.add_history('RGB image: obsolete Bayer metadata removed; no second debayer.')
        for key in ('BAYERPAT', 'XBAYROFF', 'YBAYROFF'):
            header.remove(key, ignore_missing=True, remove_all=True)
    return a, header

def luminance(a):
    return a if a.ndim == 2 else a @ np.array([0.2126, 0.7152, 0.0722])

def analyze(a, header):
    l=luminance(a)
    step=max(1,int(math.ceil(max(l.shape)/1536)))
    s=l[::step,::step]
    d=(s[:-1,:-1]-s[1:,:-1]-s[:-1,1:]+s[1:,1:])/2
    med=np.median(d)
    noise=float(np.median(np.abs(d-med))*1.4826)
    levels=np.percentile(s,[0,1,25,50,75,99,100])
    return {'shape':list(a.shape),'object':str(header.get('OBJECT',''))[:120],
            'background_estimate':float(levels[2]), 'noise_estimate':noise,
            'percentiles':dict(zip(['min','p01','p25','median','p75','p99','max'],map(float,levels))),
            'maximum_plateau_fraction':float(np.mean(s==np.max(s))),
            'sampling_step':step,
            'linearity':'Linear input is assumed; linearity cannot generally be established from the FITS header.',
            'noise_note':'Robust estimate from diagonal differences; structure, resampling and correlations may bias it.'}

def settings(raw):
    limits={'strength':(0,200,30),'denoise':(0,100,20),'detail':(0,100,0),'stretch':(1,200,30),'saturation':(0,300,100),'green_reduction':(0,100,0),'s_curve_strength':(0,100,0),'s_curve_pivot':(5,90,30),'star_brightness':(10,100,100),'star_sharpen':(0,0.7,0.1),'halo':(-0.5,0.5,0),'graxpert_smoothing':(0,1,0.5),'graxpert_sample_size':(5,101,25)}
    out={}
    for k,(low,high,default) in limits.items():
        v=float(raw.get(k,default))
        if not math.isfinite(v) or not low<=v<=high:
            raise ValueError(f'Invalid parameter {k}.')
        out[k]=v
    for k in ['gradient','protect','bxt','nxt','sxt','graxpert_gpu']:
        v=raw.get(k, k in ('protect','graxpert_gpu'))
        if not isinstance(v,bool):
            raise ValueError(f'{k} must be a boolean.')
        out[k]=v
    out['gradient_method']=raw.get('gradient_method','plane')
    if out['gradient_method'] not in ('plane','graxpert'):
        raise ValueError('Unknown gradient removal method.')
    path=raw.get('graxpert_path','')
    if not isinstance(path,str) or len(path)>2048 or any(c in path for c in ('\n','\r','\0')):
        raise ValueError('Invalid GraXpert path.')
    out['graxpert_path']=path.strip()
    out['graxpert_mode']=raw.get('graxpert_mode','ai')
    if out['graxpert_mode'] not in ('ai','rbf'):raise ValueError('Unknown GraXpert mode.')
    points=raw.get('background_points',[])
    if not isinstance(points,list) or len(points)>300:raise ValueError('Up to 300 background samples are supported.')
    out['background_points']=[]
    for point in points:
        if not isinstance(point,list) or len(point)!=2:raise ValueError('Invalid background sample.')
        xy=[float(v) for v in point]
        if not all(math.isfinite(v) and 0<=v<=1 for v in xy):raise ValueError('Background sample is outside the image.')
        if xy not in out['background_points']:out['background_points'].append(xy)
    out['graxpert_sample_size']=int(out['graxpert_sample_size'])
    return out

def process(a,p):
    strength=p['strength']/100
    b=a.copy()
    log=[]
    noise=analyze(a,{})['noise_estimate']
    if p['gradient'] and strength:
        # Fit only a plane to low-variance background cells. Not automatic nebula recognition.
        l=luminance(b); h,w=l.shape; samples=[]
        for ys in np.array_split(np.arange(h),10):
            for xs in np.array_split(np.arange(w),10):
                cell=l[np.ix_(ys,xs)]
                q25,q50,q75=np.percentile(cell,[25,50,75])
                samples.append((xs.mean()/w,ys.mean()/h,q50,q75-q25,ys,xs))
        cutoff=np.percentile([s[2] for s in samples],45)
        variance=np.percentile([s[3] for s in samples],60)
        selected=[s for s in samples if s[2]<=cutoff and s[3]<=variance]
        if len(selected)<8:
            raise ValueError('Not enough background samples for a gradient model; disable gradient removal.')
        design=np.array([[s[0],s[1],1] for s in selected])
        if np.linalg.matrix_rank(design)<3:
            raise ValueError('Background samples do not span a plane; disable gradient removal.')
        yy,xx=np.mgrid[:h,:w]; grid=np.stack([xx/w,yy/h,np.ones((h,w))],axis=-1)
        for c in range(1 if b.ndim==2 else 3):
            plane=b if b.ndim==2 else b[...,c]
            values=[np.median(plane[np.ix_(s[4],s[5])]) for s in selected]
            model=grid @ np.linalg.lstsq(design,values,rcond=None)[0]
            plane-=strength*(model-np.median(model))
        log.append('Gradient plane subtracted; this may remove extended real nebulosity. Check the difference image.')
    if p['denoise'] and strength and not p['nxt']:
        smooth=gaussian_filter(b, (0.65,0.65,0) if b.ndim==3 else 0.65)
        residual=np.abs(luminance(b-smooth))
        weights=np.exp(-residual/(max(noise,1e-12)*2)) if p['protect'] else np.ones_like(residual)
        if b.ndim==3: weights=weights[...,None]
        b+=strength*(p['denoise']/100)*weights*(smooth-b)
        log.append('Gentle weighted Gaussian denoising of linear data (not NoiseXTerminator).')
    if p['detail'] and strength and not p['bxt']:
        low=gaussian_filter(b,(1,1,0) if b.ndim==3 else 1)
        delta=b-low
        significance=np.maximum(0,1-(3*noise)/(np.abs(luminance(delta))+1e-12))
        if b.ndim==3: significance=significance[...,None]
        b+=0.25*strength*(p['detail']/100)*significance*delta
        log.append('Limited unsharp mask above estimated 3 sigma; not proof of real detail.')
    return b,log

def display_params(a):
    sample=a[::max(1,math.ceil(max(a.shape[:2])/1024)),::max(1,math.ceil(max(a.shape[:2])/1024))]
    black=float(np.percentile(sample,0.05))
    white=float(np.percentile(sample,99.95))
    return black,max(white-black,1e-12)

def stretch(a,scale,amount,saturation=100):
    black,span=scale
    x=np.maximum(0,(a-black)/span)
    k=1+amount*0.8
    x=np.arcsinh(k*x)/np.arcsinh(k)
    if x.ndim==3:
        l=luminance(x)[...,None]
        x=l+(x-l)*(saturation/100)
    return np.clip(x,0,1).astype(np.float32)

def png(a,path,maxsize=1600):
    im=Image.fromarray(np.round(np.clip(a,0,1)*255).astype('uint8'))
    im.thumbnail((maxsize,maxsize),Image.Resampling.LANCZOS)
    im.save(path)

def write_fits(a,header,path,nonlinear=False,history=()):
    h=header.copy()
    for key in ['BSCALE','BZERO','BLANK','DATAMIN','DATAMAX','CHECKSUM','DATASUM']:
        h.remove(key,ignore_missing=True,remove_all=True)
    h['APLINEAR']=not nonlinear
    if nonlinear:
        h['BUNIT']='normalized'; h.add_history('NONLINEAR display stretch, clipped to [0,1]. Not linear scientific data.')
    for line in history:
        ascii_line=unicodedata.normalize('NFKD',str(line)).encode('ascii','ignore').decode()
        h.add_history(ascii_line)
    data=np.moveaxis(a,-1,0) if a.ndim==3 else a
    fits.PrimaryHDU(data.astype(np.float32),h).writeto(path,overwrite=True,checksum=True)

def file_hash(path):
    h=hashlib.sha256()
    with open(path,'rb') as f:
        for block in iter(lambda:f.read(1024*1024),b''): h.update(block)
    return h.hexdigest()


def read_tiff(path):
    with tifffile.TiffFile(path) as tf:
        series=tf.series[0]
        if math.prod(series.shape)>MAX_SAMPLES:
            raise ValueError('TIFF exceeds the limit of 120 million samples.')
        if series.dtype.kind not in ('u','i','f') or series.dtype.itemsize<2:
            raise ValueError('TIFF must contain at least 16-bit integer or 32/64-bit floating-point data. 8-bit TIFF is not accepted.')
        if any(p.photometric not in (0,1,2) for p in tf.pages):
            raise ValueError('Only monochrome MINISBLACK and RGB TIFF are supported; palette/CMYK TIFF is not supported.')
        if any(p.photometric==0 for p in tf.pages):
            raise ValueError('MINISWHITE TIFF is not supported as linear astronomical input.')
        a=series.asarray().astype(np.float64)
        axes=series.axes
    if a.ndim==3:
        if axes in ('SYX','CYX') and a.shape[0]==3:
            a=np.moveaxis(a,0,-1)
        elif axes not in ('YXS','YXC') or a.shape[-1]!=3:
            raise ValueError('TIFF must be monochrome or three-channel RGB, without alpha or additional image pages.')
    elif a.ndim!=2:
        raise ValueError('Only 2D monochrome or RGB TIFF is supported.')
    if min(a.shape[:2])<16 or not np.isfinite(a).all():
        raise ValueError('TIFF is too small or contains NaN/Inf.')
    header=fits.Header()
    header['ORIGFMT']='TIFF'
    header.add_history('TIFF import; linear input assumed. No WCS or exposure metadata inferred.')
    return a,header


def reduce_green_display(image,amount):
    """Suppress only excess green in stretched RGB. Not statistical denoising."""
    if not amount or image.ndim!=3:
        return image
    out=image.copy()
    neutral_ceiling=np.maximum(out[...,0],out[...,2])
    excess=np.maximum(0,out[...,1]-neutral_ceiling)
    out[...,1]-=(amount/100)*excess
    return out


def apply_s_curve(image,strength,pivot):
    """Monotonic luminance S-curve on display data, with hue-preserving gamut limit."""
    if not strength:return image
    x=np.clip(luminance(image),0,1).astype(np.float64)
    center=pivot/100;gamma=1+3*strength/100
    mapped=np.where(x<=center,center*(x/center)**gamma,1-(1-center)*((1-x)/(1-center))**gamma)
    if image.ndim==2:return mapped.astype(np.float32)
    ratio=np.divide(mapped,x,out=np.ones_like(x),where=x>1e-12)
    peak=np.max(image,axis=-1)
    gamut=np.divide(1,peak,out=np.full_like(x,np.inf),where=peak>1e-12)
    ratio=np.minimum(ratio,gamut)
    return np.clip(image*ratio[...,None],0,1).astype(np.float32)


def measure_sample_noise(a,points,sample_size):
    """Robust MAD sigma after iterative local-plane detrending in original linear samples."""
    h,w=a.shape[:2];half=sample_size//2
    def estimate(plane):
        yy,xx=np.mgrid[:plane.shape[0],:plane.shape[1]]
        design=np.column_stack([xx.ravel()-xx.mean(),yy.ravel()-yy.mean(),np.ones(plane.size)])
        values=plane.ravel();mask=np.ones(plane.size,dtype=bool)
        for _ in range(4):
            if mask.sum()<max(12,int(plane.size*0.5)):raise ValueError('Too few retained pixels for a noise estimate.')
            fit=np.linalg.lstsq(design[mask],values[mask],rcond=None)[0]
            residual=values-design@fit
            center=np.median(residual[mask])
            sigma=float(1.4826022185*np.median(np.abs(residual[mask]-center)))
            if sigma<=np.finfo(float).eps*max(1,float(np.max(np.abs(values)))):break
            next_mask=np.abs(residual-center)<=3.5*sigma
            if np.array_equal(next_mask,mask):break
            mask=next_mask
        fit=np.linalg.lstsq(design[mask],values[mask],rcond=None)[0]
        residual=values-design@fit
        sigma=float(1.4826022185*np.median(np.abs(residual[mask]-np.median(residual[mask]))))
        return {'sigma':sigma,'level':float(np.median(values[mask])),
                'excluded_fraction':float(1-mask.mean()),'retained_pixels':int(mask.sum())}
    rows=[]
    for index,(nx,ny) in enumerate(points,1):
        x,y=round(nx*(w-1)),round(ny*(h-1))
        row={'index':index,'x':x,'y':y,'valid':False}
        if x-half<0 or y-half<0 or x+half>=w or y+half>=h:
            row['reason']='Sample extends beyond the image edge.';rows.append(row);continue
        patch=a[y-half:y+half+1,x-half:x+half+1]
        try:
            result=estimate(luminance(patch))
            row.update(valid=True,noise_sigma=result['sigma'],background_level=result['level'],
                       excluded_fraction=result['excluded_fraction'],retained_pixels=result['retained_pixels'],
                       actual_sample_size=patch.shape[0])
            if a.ndim==3:row['channel_sigma']={c:estimate(patch[...,i])['sigma'] for i,c in enumerate('RGB')}
        except ValueError as exc:row['reason']=str(exc)
        rows.append(row)
    valid=[r for r in rows if r['valid']]
    sigmas=[r['noise_sigma'] for r in valid]
    return {'noise_sigma':float(np.median(sigmas)) if sigmas else None,
            'background_level':float(np.median([r['background_level'] for r in valid])) if valid else None,
            'sigma_iqr':list(map(float,np.percentile(sigmas,[25,75]))) if sigmas else None,
            'valid_samples':len(valid),'total_samples':len(rows),'samples':rows,
            'method':'Median of sample MAD sigma after local-plane removal and iterative 3.5-sigma rejection.',
            'units':'Original input data units; RGB noise is measured in weighted luminance.',
            'note':'Measured before gradient removal, denoising and stretching. This is not SNR. Nebulosity, unresolved stars and correlated/resampled noise may bias estimates.'}
