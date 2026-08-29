from fastapi import APIRouter, Depends, File, UploadFile, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.auth import get_current_user
from app.database import get_db
from app.models import Beat, User
from app.audio_store import save_upload, path_for
router=APIRouter()

@router.post('/{beat_id}')
def upload_audio(beat_id:int,file:UploadFile=File(...),db:Session=Depends(get_db),current_user:User=Depends(get_current_user)):
    beat=db.scalar(select(Beat).where(Beat.id==beat_id,Beat.user_id==current_user.id))
    if not beat: raise HTTPException(404,'Beat not found')
    filename,path=save_upload(beat_id,file); beat.audio_filename=filename; beat.audio_path=path; db.commit()
    return {'status':'ok','beat_id':beat_id,'filename':filename}

@router.get('/{beat_id}')
def download_audio(beat_id:int,db:Session=Depends(get_db),current_user:User=Depends(get_current_user)):
    beat=db.get(Beat,beat_id)
    if not beat or not beat.audio_path: raise HTTPException(404,'Audio not found')
    p=path_for(beat.audio_path)
    if not p.is_file(): raise HTTPException(404,'Audio file not found on server')
    # A beat is downloadable only to users who have the beat in their catalog or an attached sale.
    from app.models import BeatSend, License
    allowed=beat.user_id==current_user.id or db.scalar(select(BeatSend.id).where(BeatSend.user_id==current_user.id,BeatSend.beat_id==beat_id)) or db.scalar(select(License.id).where(License.user_id==current_user.id,License.beat_id==beat_id))
    if not allowed: raise HTTPException(403,'Audio access denied')
    return FileResponse(p,media_type='audio/mpeg',filename=beat.audio_filename or 'beat.mp3')
