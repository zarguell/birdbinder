import pytest


@pytest.mark.asyncio
async def test_search_species_by_common_name(auth_client):
    r = await auth_client.get("/api/species/search?q=robin&limit=100")
    assert r.status_code == 200
    data = r.json()
    assert data["total"] > 0
    assert any(b["common_name"] == "American Robin" for b in data["items"])


@pytest.mark.asyncio
async def test_search_species_by_scientific_name(auth_client):
    r = await auth_client.get("/api/species/search?q=Turdus")
    assert r.status_code == 200
    assert any("Turdus" in b["scientific_name"] for b in r.json()["items"])


@pytest.mark.asyncio
async def test_search_species_pagination(auth_client):
    r = await auth_client.get("/api/species/search?q=a&limit=5&offset=0")
    assert len(r.json()["items"]) <= 5


@pytest.mark.asyncio
async def test_search_species_empty(auth_client):
    r = await auth_client.get("/api/species/search?q=zzzzznotarealbird")
    assert r.json()["items"] == []
    assert r.json()["total"] == 0


@pytest.mark.asyncio
async def test_get_species_by_code(auth_client):
    r = await auth_client.get("/api/species/amerob")
    assert r.status_code == 200
    assert r.json()["common_name"] == "American Robin"
    assert r.json()["species_code"] == "amerob"


@pytest.mark.asyncio
async def test_get_species_not_found(auth_client):
    r = await auth_client.get("/api/species/notexist")
    assert r.status_code == 404


def test_service_search_directly():
    from app.services.species import search_species

    results, total = search_species("eagle")
    assert total > 0
    assert len(results) > 0
    assert results[0]["species_code"]


def test_service_get_by_code():
    from app.services.species import get_species_by_code

    sp = get_species_by_code("amecro")
    assert sp is not None
    assert sp["common_name"] == "American Crow"
