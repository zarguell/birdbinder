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


def test_service_search_with_family_filter():
    from app.services.species import search_species

    results, total = search_species("duck", family="Ducks, Geese, and Waterfowl")
    assert total > 0
    for r in results:
        assert r["family"] == "Ducks, Geese, and Waterfowl"

    # No match when wrong family
    results2, total2 = search_species("eagle", family="Ducks, Geese, and Waterfowl")
    assert total2 == 0


def test_service_list_families():
    from app.services.species import list_families

    families = list_families()
    assert isinstance(families, list)
    assert len(families) > 100
    for f in families[:5]:
        assert "name" in f
        assert "species_count" in f
        assert f["species_count"] > 0
    # Should be sorted alphabetically
    names = [f["name"] for f in families]
    assert names == sorted(names)


@pytest.mark.asyncio
async def test_search_species_with_family_filter(auth_client):
    resp = await auth_client.get(
        "/api/species/search?q=duck&family=Ducks, Geese, and Waterfowl"
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] > 0
    for item in data["items"]:
        assert item["family"] == "Ducks, Geese, and Waterfowl"


@pytest.mark.asyncio
async def test_search_species_no_match_with_family_filter(auth_client):
    resp = await auth_client.get(
        "/api/species/search?q=eagle&family=Ducks, Geese, and Waterfowl"
    )
    assert resp.status_code == 200
    assert resp.json()["total"] == 0


@pytest.mark.asyncio
async def test_list_families(auth_client):
    resp = await auth_client.get("/api/species/families")
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    assert len(data) > 100
    for fam in data[:5]:
        assert "name" in fam
        assert "species_count" in fam
        assert fam["species_count"] > 0


@pytest.mark.asyncio
async def test_search_results_sorted_by_taxon_order(auth_client):
    resp = await auth_client.get("/api/species/search?q=sparrow&limit=50")
    assert resp.status_code == 200
    items = resp.json()["items"]
    if len(items) >= 2:
        orders = [item.get("taxon_order", 99999) for item in items]
        assert orders == sorted(orders), "Results should be sorted by taxon_order"
