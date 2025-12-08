from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Dict, List, Sequence

import requests

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class USDAFoodDataClient:
    """Thin wrapper around the USDA FoodData Central API."""

    api_key: str
    base_url: str = "https://api.nal.usda.gov/fdc/v1"
    timeout: float = 5.0

    _DEFAULT_DATA_TYPES: Sequence[str] = (
        "Foundation",
        "SR Legacy",
        "Survey (FNDDS)"
    )

    def _post(self, endpoint: str, payload: Dict) -> Dict:
        if not self.api_key:
            raise ValueError("USDA API key is required for USDAFoodDataClient")

        url = f"{self.base_url.rstrip('/')}/{endpoint.lstrip('/')}"
        params = {"api_key": self.api_key}
        resp = requests.post(url, params=params, json=payload, timeout=self.timeout)
        resp.raise_for_status()
        return resp.json()

# ... imports / dataclass header unchanged ...

    def search_foods(
        self,
        query: str,
        *,
        page_size: int = 5,
        data_types: Sequence[str] | None = None,
    ) -> List[Dict]:
        if not query:
            return []

        payload = {
            "query": query,
            "pageSize": page_size,
            "requireAllWords": True,
            "dataType": list(data_types or self._DEFAULT_DATA_TYPES),  # <— honor caller
        }

        try:
            data = self._post("foods/search", payload)
        except requests.HTTPError as exc:
            logger.warning("USDA search failed for '%s': %s", query, exc)
            return []
        except requests.RequestException as exc:
            logger.warning("USDA search request issue for '%s': %s", query, exc)
            return []

        foods = data.get("foods")
        if not isinstance(foods, list):
            logger.debug("Unexpected USDA payload for '%s': %s", query, data)
            return []
        return foods

