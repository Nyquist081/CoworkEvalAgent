from fastapi.testclient import TestClient


# We need a minimal app for testing
def test_router_creation():
    from src.api.router import api_router
    assert api_router.prefix == "/coworkeval/v1"
    # Should have routes for runs, scores, manifests, comparison, meta, websocket
    route_paths = [r.path for r in api_router.routes]
    assert any("/runs" in p for p in route_paths)
    assert any("/scores" in p for p in route_paths)
    assert any("/manifests" in p for p in route_paths)
    assert any("/compare" in p for p in route_paths)
    assert any("/meta" in p for p in route_paths)
    assert any("/ws" in p for p in route_paths)
