# Stories 4+5: Location Override + Species Taxonomy Dropdown

## Story 4: Location Override on Sightings

### Goal
Allow users to edit the lat/lng on a sighting to correct GPS errors or add location for photos without EXIF.

### Tasks
- **4.1** Add `latitude`/`longitude` nullable Float columns to sightings model + Alembic migration
- **4.2** Add `PATCH /sightings/{id}` endpoint that accepts optional lat/lng fields (only updates provided fields, preserves others)
- **4.3** Frontend: show lat/lng on sighting detail page (if present) with edit button/capability
- **4.4** Tests: migration, API update, validation (lat -90..90, lng -180..180)

## Story 5: Species Taxonomy Dropdown

### Goal
Replace free-text species search with a proper searchable dropdown backed by the existing species data.

### Tasks
- **5.1** Enhance `GET /species/search` to support filtering by family, ordering by taxonomy
- **5.2** Frontend: build species selector component (search input + dropdown with family grouping)
- **5.3** Wire species selector into sighting detail page as manual override option
- **5.4** Tests: search with filters, pagination, ordering
