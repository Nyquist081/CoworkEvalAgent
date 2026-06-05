from fastapi import APIRouter, HTTPException, UploadFile, File
from src.core.schemas import Manifest
from src.repositories.manifest_repository import ManifestRepository
from src.infrastructure.database import async_session
import json

router = APIRouter(prefix="/manifests")

def _repo():
    return ManifestRepository(async_session)


@router.get("", response_model=list[Manifest])
async def list_manifests():
    return await _repo().list_all()


@router.post("", response_model=Manifest, status_code=201)
async def register_manifest(manifest: Manifest):
    existing = await _repo().get(manifest.benchmark_id)
    if existing:
        raise HTTPException(409, f"Already exists: {manifest.benchmark_id}")
    return await _repo().save(manifest)


@router.post("/upload", response_model=Manifest, status_code=201)
async def upload_manifest(file: UploadFile = File(...)):
    content = await file.read()
    manifest = Manifest.model_validate(json.loads(content))
    return await _repo().save(manifest)


@router.get("/{benchmark_id}", response_model=Manifest)
async def get_manifest(benchmark_id: str):
    m = await _repo().get(benchmark_id)
    if not m:
        raise HTTPException(status_code=404)
    return m
