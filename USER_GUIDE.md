# BirdBinder — User Guide

## Getting Started

Open the app in your browser. If your instance is behind Cloudflare Access, you'll be prompted to sign in — your email is your identity.

### Upload a Sighting

1. Go to **Upload** (camera icon in the nav)
2. Take a photo with your camera or choose an image file
3. Optionally add notes or a location name
4. Tap **Submit Sighting**

Your photo is sent to the AI for identification. This runs in the background, so you can keep browsing.

### View Identification Results

1. Go to **Sightings** from the nav
2. Tap any sighting to see its detail page
3. Statuses:
   - **Pending** — AI is still analyzing the photo
   - **Identified** — AI found a match (species, confidence, pose)
   - **Failed** — identification didn't work (bad photo, no API key, etc.)
   - **Manual** — you overrode the AI guess

You can always tap **Override** to manually set the species if the AI got it wrong.

## Cards

Once a sighting is identified, tap **Generate Card** on the sighting detail page. A background job creates a collectible card from the sighting.

- **Card art** — if an AI image model is configured, a stylized illustration is generated. Otherwise, your original photo is used.
- **Rarity** — automatically assigned based on eBird taxonomy frequency: Common, Uncommon, Rare, Epic, or Legendary.
- **Duplicates** — if you already have a card for that species, the duplicate counter increments and the card becomes tradeable.

View all your cards from the **Cards** tab.

## Binders

Binders are collections you organize yourself.

1. Go to **Binders** → **Create Binder**
2. Give it a name and optional description
3. Open the binder and tap **Add Cards** to pick cards from your collection
4. Drag to reorder cards within the binder

Each binder shows a card count and can be filtered by rarity or species.

## Sets

Sets are themed collections with specific card targets (like a checklist — "Winter Warblers of the Northeast").

1. Go to **Sets** → **Create Set**
2. Name it, choose a region/season, and define which cards are needed
3. The set detail page shows completion progress — which cards you have and which are still missing

## Trading

Trade cards with other users on the same instance.

1. Go to **Trades** → **Create Trade**
2. Select cards from your collection to offer
3. Pick a user to trade with and select cards you want from them
4. The other user sees the offer on their Trades page and can **Accept** or **Decline**

Only cards with duplicates (`duplicate_count > 0`) are tradeable — you can't trade your only copy of a card.

## Rarity Tiers

| Tier | Description |
|------|-------------|
| **Common** | Widespread species seen frequently |
| **Uncommon** | Regional or seasonal species |
| **Rare** | Unusual sightings, limited range |
| **Epic** | Very uncommon, notable find |
| **Legendary** | Exceptionally rare or vagrant species |

Rarity is assigned automatically based on eBird taxonomy data (~17,000 species).

## Tips

- **Photo quality matters** — clear, well-lit photos with the bird prominently visible get better AI identifications
- **Check your pending sightings** — AI jobs run in the background, so check back if a sighting is still "Pending"
- **Override freely** — if the AI is wrong, tap Override and set the correct species manually
- **Build sets strategically** — sets with specific regions/seasons make collecting feel like a real checklist
- **Trade duplicates** — once you have 2+ of a card, the extra becomes tradeable
