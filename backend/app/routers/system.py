from fastapi import APIRouter
from app.config import settings
import os
router=APIRouter()
APP_VERSION='0.27.0'
@router.get('/version')
def version():
    latest=os.getenv('DD_LATEST_VERSION', APP_VERSION)
    update_url=os.getenv('DD_UPDATE_URL') or None
    return {'app':'D&D','version':APP_VERSION,'latest_version':latest,'channel':'stable','update_available':latest != APP_VERSION,'update_url':update_url}
