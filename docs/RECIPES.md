# Recipes And Pantry

Recipes are local-first. The current implementation supports:

- pantry items stored in SQLite
- recipe and ingredient storage
- deterministic ingredient matching
- missing required ingredient calculation
- additional cheapest cost from cached offers

Pantry matching intentionally requires stronger confidence than offer matching. It is safer to say an ingredient is missing than to silently replace it with something unrelated.

Future work:

- servings-aware quantities
- cost per serving
- dietary tags
- recipe UI
- integrated route and basket recommendations
