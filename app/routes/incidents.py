from fastapi import APIRouter, UploadFile, File
from app.schemas import IncidentCreate
from app.utils.packager import package_evidence
import uuid, os

router = APIRouter()

@router.post('/report')
async def report(inc: IncidentCreate, files: list[UploadFile] = File(None)):
    saved = []
    if files:
        for f in files:
            fname = f"/tmp/{uuid.uuid4().hex}_{f.filename}"
            with open(fname,'wb') as out:
                out.write(await f.read())
            saved.append(fname)
    meta = {'title': inc.title, 'desc': inc.description, 'lat': inc.lat, 'lon': inc.lon, 'auto': inc.auto}
    evidence_hash, pkg_path = package_evidence(meta, saved)
    return {'incident_id': uuid.uuid4().hex, 'evidence_hash': evidence_hash, 'pkg': pkg_path}

@router.get('/{id}')
async def get_incident(id: str):
    return {'id': id, 'status':'new'}

@router.post('/{id}/anchor')
async def anchor(id: str):
    return {'id': id, 'anchored': True, 'tx': '0xDEMO'}
