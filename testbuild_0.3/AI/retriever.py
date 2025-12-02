# Takes normalized ingredient terms and returns the RetrievalBatch shape
# Stub retriever for local testing and USDA-backed retriever.

from __future__ import annotations

import logging
import os
import re
from dataclasses import dataclass
from typing import List, Protocol, Sequence, Set

from .retrieval_contract import IngredientFact, NutritionBreakdown, RetrievalBatch
from .usda_client import USDAFoodDataClient

logger = logging.getLogger(__name__)

# ---------------- Config (generic) ----------------
USE_RERANK = (os.getenv("USDA_RERANK", "on").lower() != "off")

_RECOMMENDED_TYPES: Sequence[str] = (
    "Foundation",
    "SR Legacy",
    "Survey (FNDDS)",
)
if os.getenv("USDA_INCLUDE_BRANDED", "false").lower() == "true":
    _RECOMMENDED_TYPES = (*_RECOMMENDED_TYPES, "Branded")

_DATASET_WEIGHT = {
    "foundation": 3.0,
    "sr legacy": 2.5,
    "survey (fndds)": 2.0,
    "branded": 1.0,
}

# Tokens that are “format/cooking/size” modifiers (not ingredients)
_GENERIC_MODIFIERS = {
    "raw","fresh","cooked","boiled","fried","baked","roasted","grilled",
    "large","medium","small","whole","chopped","sliced","diced","cup","tbsp","tsp",
}

_OIL_TOKENS = {"oil","butter","shortening","lard","fat"}

_GRAMS_PER_OUNCE = 28.3495
_GRAMS_PER_POUND = 453.59237

# FDC nutrientId → our keys (we normalize to per 100 g)
_NUTRIENT_ID_MAP = {
    1008: "calories",
    1003: "protein_g",
    1005: "carbs_g",
    1004: "fats_g",
}

# -------------- Interface -----------------
class IngredientRetriever(Protocol):
    def fetch(self, ingredient_names: Sequence[str]) -> RetrievalBatch: ...

# -------------- Stub (unchanged) ----------
@dataclass(slots=True)
class StubIngredientRetriever:
    store: dict[str, IngredientFact]

    def fetch(self, ingredient_names: Sequence[str]) -> RetrievalBatch:
        normalized = [n.strip().lower() for n in ingredient_names if n.strip()]
        facts: List[IngredientFact] = []
        missing: List[str] = []
        for name in normalized:
            fact = self.store.get(name)
            facts.append(fact) if fact else missing.append(name)
        batch = RetrievalBatch(query_terms=list(normalized), facts=facts)
        if missing:
            batch.warnings.append(f"No facts available for: {', '.join(sorted(set(missing)))}")
        return batch

DEFAULT_STUB_STORE = {
    # (kept minimal; doesn’t affect USDA path)
}

# -------------- USDA retriever ------------
@dataclass(slots=True)
class USDAIngredientRetriever:
    client: USDAFoodDataClient
    page_size: int = int(os.getenv("USDA_PAGE_SIZE", "8") or 8)
    data_types: Sequence[str] = _RECOMMENDED_TYPES
    min_match_ratio: float = float(os.getenv("USDA_MIN_MATCH", "0.40") or 0.40)

    def fetch(self, terms: Sequence[str]) -> RetrievalBatch:
        facts: List[IngredientFact | None] = []
        qterms = [t for t in terms if (t or "").strip()]
        for term in qterms:
            items = self.client.search_foods(term, page_size=self.page_size, data_types=self.data_types)
            if not items:
                logger.debug("USDA: no results for %s", term)
                facts.append(None)
                continue

            tokens = self._tokenize(term)
            picked = self._select_food(term, tokens, items) if USE_RERANK else items[0]
            fact = self._food_to_fact(term, picked)
            if fact is None:
                # fall back to first usable item if our pick fails sanity
                for alt in items:
                    fact = self._food_to_fact(term, alt)
                    if fact:
                        picked = alt
                        break
            facts.append(fact)

            # Debug: show what we used
            if picked:
                logger.debug("USDA pick for '%s' → %s (fdcId=%s)",
                             term, picked.get("description","?"), picked.get("fdcId"))
        return RetrievalBatch(query_terms=list(qterms), facts=facts)

    # ---------------- helpers ----------------
    @staticmethod
    def _tokenize(text: str) -> Set[str]:
        parts = re.split(r"[^a-z0-9]+", (text or "").lower())
        return {p for p in parts if p}

    @classmethod
    def _trim_modifiers(cls, tokens: Set[str]) -> Set[str]:
        return {t for t in tokens if t not in _GENERIC_MODIFIERS}

    @classmethod
    def _token_overlap(cls, query_tokens: Set[str], text: str) -> float:
        desc_tokens = cls._tokenize(text)
        if not desc_tokens or not query_tokens:
            return 0.0
        q = cls._trim_modifiers(query_tokens)
        d = cls._trim_modifiers(desc_tokens)
        if not q or not d:
            return 0.0
        inter = len(q & d)
        return inter / len(q)

    def _score(self, term_tokens: Set[str], food: dict) -> tuple[float, float]:
        desc = (food.get("description") or "").lower()
        data_type = (food.get("dataType") or "").lower()
        overlap = self._token_overlap(term_tokens, desc)

        # dataset priority
        ds = _DATASET_WEIGHT.get(data_type, 0.0)

        # concision: prefer shorter descriptions after removing modifiers
        d_tokens = self._trim_modifiers(self._tokenize(desc))
        q_tokens = self._trim_modifiers(term_tokens)
        concision = 0.0
        if d_tokens:
            concision = min(1.0, len(q_tokens) / len(d_tokens))  # in [0..1]

        score = 3.0 * overlap + 1.0 * ds + 0.5 * concision
        return score, overlap

    def _select_food(self, term: str, term_tokens: Set[str], foods: List[dict]) -> dict:
        scored: List[tuple[float, float, dict]] = []
        for f in foods:
            s, ov = self._score(term_tokens, f)
            scored.append((s, ov, f))
        if not scored:
            return foods[0]
        # prefer strong overlaps; else best score
        strict = [t for t in scored if t[1] >= self.min_match_ratio]
        pool = strict or scored
        pool.sort(key=lambda t: (t[1], t[0]), reverse=True)
        return pool[0][2]

    def _food_to_fact(self, query: str, food: dict) -> IngredientFact | None:
        nutrients = {n.get("nutrientId"): n for n in (food.get("foodNutrients") or []) if isinstance(n, dict)}
        vals = {"calories": 0.0, "protein_g": 0.0, "carbs_g": 0.0, "fats_g": 0.0}
        for nid, key in _NUTRIENT_ID_MAP.items():
            node = nutrients.get(nid)
            if node is None: 
                continue
            try:
                vals[key] = float(node.get("value") or 0.0)
            except (TypeError, ValueError):
                vals[key] = 0.0

        if vals["calories"] <= 0:
            return None

        raw_serving = self._serving_size_in_grams(food)
        data_type = (food.get("dataType") or "").strip().lower()
        # Foundation/SR/Survey data already reports per 100 g; Branded entries are per serving.
        basis_g = raw_serving if (data_type == "branded" and raw_serving) else 100.0

        # sanity: kcal/g
        desc_lc = (food.get("description") or "").lower()
        is_fatty = any(t in desc_lc for t in _OIL_TOKENS)
        kcal_per_g = (vals["calories"] / basis_g) if (vals["calories"] and basis_g) else 0.0
        if kcal_per_g > 6.5 and not is_fatty:
            return None

        try:
            nutrition = NutritionBreakdown(
                serving_size_g=basis_g,
                calories=vals["calories"],
                protein_g=vals["protein_g"],
                carbs_g=vals["carbs_g"],
                fats_g=vals["fats_g"],
            )
        except (TypeError, ValueError):
            return None

        summary = "; ".join(
            p for p in [(food.get("description") or ""), (food.get("foodCategory") or "")]
            if p
        ).strip() or "Nutrition facts"

        tags: List[str] = []
        if food.get("foodCategory"): tags.append(food["foodCategory"])
        if food.get("dataType"):     tags.append(food["dataType"])

        return IngredientFact(
            canonical_name=(food.get("description") or query).lower(),
            source_id=f"fdc:{food.get('fdcId')}",
            summary=summary,
            nutrition=nutrition,
            tags=tags,
            source_serving_size_g=raw_serving,
        )

    @staticmethod
    def _serving_size_in_grams(food: dict) -> float | None:
        size = food.get("servingSize")
        unit = (food.get("servingSizeUnit") or "").strip().lower()
        try:
            value = float(size)
        except (TypeError, ValueError):
            return None
        if value <= 0:
            return None
        if unit in {"g", "gram", "grams"}:
            return value
        if unit in {"oz", "ounce", "ounces"}:
            return value * _GRAMS_PER_OUNCE
        if unit in {"lb", "pound", "pounds"}:
            return value * _GRAMS_PER_POUND
        if unit in {"kg", "kilogram", "kilograms"}:
            return value * 1000.0
        return None

