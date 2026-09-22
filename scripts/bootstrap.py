#!/usr/bin/env python3
"""Cross-platform install/build; credentials are entered only in the local UI."""
import argparse,os,shutil,subprocess,sys,venv
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def run(cmd,cwd=ROOT):subprocess.run(cmd,cwd=cwd,check=True)
def main():
 p=argparse.ArgumentParser();p.add_argument('--run',action='store_true');a=p.parse_args()
 if sys.version_info<(3,10):raise SystemExit('Python 3.10 이상이 필요합니다.')
 python=ROOT/'.venv'/('Scripts/python.exe' if os.name=='nt' else 'bin/python')
 if not python.exists():venv.create(ROOT/'.venv',with_pip=True)
 run([str(python),'-m','pip','install','--require-hashes','-r','requirements.txt'])
 npm=shutil.which('npm.cmd' if os.name=='nt' else 'npm')
 if not npm:raise SystemExit('Node.js 22 LTS 설치 후 다시 실행하세요.')
 run([npm,'ci'],ROOT/'frontend');run([npm,'run','build'],ROOT/'frontend')
 print('준비 완료: '+str(python)+' server.py')
 if a.run:run([str(python),'server.py','--open'])
if __name__=='__main__':main()
