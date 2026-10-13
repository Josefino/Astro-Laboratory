"""Run with build-venv Python on the native Windows/macOS platform."""
import argparse
import os
from pathlib import Path
import platform
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[1]
VERSION='0.8.0'
NAME='AstroLaboratory'


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--console',action='store_true');args=parser.parse_args()
    if sys.platform not in ('win32','darwin'):
        raise SystemExit('Build Windows on Windows and macOS on macOS.')
    if sys.version_info<(3,11):raise SystemExit('Python 3.11+ is required; Python 3.12 is recommended.')
    if sys.maxsize<=2**32:raise SystemExit('Use 64-bit Python to build this application.')
    cmd=[sys.executable,'-m','PyInstaller','--noconfirm','--clean','--onedir','--name',NAME,
         '--distpath',str(ROOT/'dist'),'--workpath',str(ROOT/'build/pyinstaller'),'--specpath',str(ROOT/'build'),
         '--add-data',str(ROOT/'static')+os.pathsep+'static',
         '--collect-all','astropy','--collect-all','scipy','--collect-all','tifffile',
         '--collect-all','PIL','--copy-metadata','flask','--copy-metadata','werkzeug']
    if not args.console:cmd.append('--windowed')
    if sys.platform=='darwin':
        cmd.extend(['--osx-bundle-identifier','local.astroprocessor.desktop'])
        if os.environ.get('CODESIGN_IDENTITY'):cmd.extend(['--codesign-identity',os.environ['CODESIGN_IDENTITY']])
    else:cmd.extend(['--version-file',str(ROOT/'packaging/windows_version.txt')])
    cmd.append(str(ROOT/'desktop_launcher.py'))
    subprocess.run(cmd,cwd=ROOT,check=True)
    print(f'Built {NAME} {VERSION} for {sys.platform} ({platform.machine()}).')


if __name__=='__main__':main()
