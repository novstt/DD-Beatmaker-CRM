from pathlib import Path
import os, re
from fastapi import UploadFile, HTTPException
BASE=Path(os.getenv("DD_AUDIO_DIR","/data/audio"))
BASE.mkdir(parents=True,exist_ok=True)

def safe_name(name):
    name=Path(name or "beat.mp3").name
    name=re.sub(r"[^A-Za-z0-9._ -]","_",name)
    return name if name.lower().endswith('.mp3') else name+'.mp3'

def save_upload(beat_id:int, upload:UploadFile):
    filename=safe_name(upload.filename)
    if not filename.lower().endswith('.mp3'): raise HTTPException(422,'Only MP3 files are supported')
    dest=BASE/f"beat_{beat_id}.mp3"
    with dest.open('wb') as f:
        while chunk:=upload.file.read(1024*1024): f.write(chunk)
    return filename,str(dest)

def path_for(path):
    p=Path(path or '')
    if not p.is_absolute(): p=BASE/p
    return p
