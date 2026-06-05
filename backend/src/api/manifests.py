from fastapi import APIRouter, HTTPException
from src.core.schemas import Manifest

router = APIRouter(prefix="/manifests")

_manifests_store: dict[str, Manifest] = {}


@router.get("", response_model=list[Manifest])
async def list_manifests():
    return list(_manifests_store.values())


@router.post("", response_model=Manifest, status_code=201)
async def register_manifest(manifest: Manifest):
    _manifests_store[manifest.benchmark_id] = manifest
    return manifest


@router.get("/{benchmark_id}", response_model=Manifest)
async def get_manifest(benchmark_id: str):
    m = _manifests_store.get(benchmark_id)
    if not m:
        raise HTTPException(status_code=404, detail="Manifest not found")
    return m
