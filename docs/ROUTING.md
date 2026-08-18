# Routing

The current routing foundation is deliberately small:

- Haversine distance between coordinates
- walking-time estimate
- nearby merchant sorting
- duplicate merchant warnings

No map SDK is required for core functionality. If maps or routing providers are unavailable, the app should fall back to merchant lists, distances, and itineraries.

Future work:

- multi-stop route optimization
- price vs distance scoring
- Android mapping intents
- optional map screen
