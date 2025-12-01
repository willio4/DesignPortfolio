# DesignPortfolio
Fall '25 Design Portfolio

## Ingredient Retrieval

The meal generator now supports two ingredient-fact sources:

- **Stub** (default): in-memory spinach/salmon facts for offline testing.
- **USDA FoodData Central**: live nutrition pulled via the USDA API.

To enable USDA, set the following environment variables before starting Flask:

```
export INGREDIENT_RETRIEVER=usda
export USDA_API_KEY="your-key-here"
# optional: override how many USDA results to scan per term (default 3)
export USDA_PAGE_SIZE=5
```

The USDA client uses the `requests` library; install it in your virtualenv if it's not already available (`pip install requests`).

If the key is missing or a request fails, the app automatically falls back to the stub retriever so development can continue without network access.
