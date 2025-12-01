# Takes normalized ingredient terms and returns the RetrievalBatch shape
# from retrieval_contract.py
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

# ---------------------------------------------------------------------------
# Rerank controls (soft; turn off with USDA_RERANK=off)
# ---------------------------------------------------------------------------
USE_RERANK = (os.getenv("USDA_RERANK", "on").lower() != "off")

# Prefer unbranded datasets by default; include Branded only if you want brand-specific lookups
RETRIEVER_DATA_TYPES: Sequence[str] = tuple(
    (os.getenv("USDA_INCLUDE_BRANDED", "false").lower() == "true")
    and ("Foundation", "SR Legacy", "Survey (FNDDS)", "Branded")
    or ("Foundation", "SR Legacy", "Survey (FNDDS)")
)

_PREFERRED_DATASETS = {"foundation", "sr legacy", "survey (fndds)"}
_OIL_TOKENS = {"oil", "butter", "shortening", "lard", "fat"}

# FDC nutrientId mapping (we normalize to per 100 g downstream)
_NUTRIENT_ID_MAP = {
    1008: "calories",   # Energy (kcal)
    1003: "protein_g",  # Protein (g)
    1005: "carbs_g",    # Carbohydrate (g)
    1004: "fats_g",     # Total lipid (fat) (g)
}


# Ingredient retriever interface
class IngredientRetriever(Protocol):
    def fetch(self, ingredient_names: Sequence[str]) -> RetrievalBatch:
        ...


@dataclass(slots=True)
class StubIngredientRetriever:
    # In-memory retriever for local testing until USDA is wired up.
    store: dict[str, IngredientFact]

    def fetch(self, ingredient_names: Sequence[str]) -> RetrievalBatch:
        normalized = [name.strip().lower() for name in ingredient_names if name.strip()]
        facts: List[IngredientFact] = []
        missing: List[str] = []

        for name in normalized:
            fact = self.store.get(name)
            if fact:
                facts.append(fact)
            else:
                missing.append(name)

        batch = RetrievalBatch(query_terms=list(normalized), facts=facts)
        if missing:
            batch.warnings.append(
                f"No facts available for: {', '.join(sorted(set(missing)))}"
            )
        return batch


DEFAULT_STUB_STORE = {
    "spinach": IngredientFact(
        canonical_name="spinach",
        source_id="stub:spinach",
        summary="Leafy green rich in iron and vitamin K.",
        nutrition=NutritionBreakdown(
            serving_size_g=30,
            calories=23,
            protein_g=2.9,
            carbs_g=3.6,
            fats_g=0.4,
            micros={"iron": 2.7, "vitamin_k": 145},
        ),
        tags=["leafy-green"],
    ),
    "salmon": IngredientFact(
        canonical_name="salmon",
        source_id="stub:salmon",
        summary="Fatty fish high in omega-3s and protein.",
        nutrition=NutritionBreakdown(
            serving_size_g=85,
            calories=175,
            protein_g=19.9,
            carbs_g=0,
            fats_g=10.5,
            micros={"omega_3": 1.5},
        ),
        tags=["seafood", "omega-3"],
    ),
}


@dataclass(slots=True)
class USDAIngredientRetriever:
    client: USDAFoodDataClient
    page_size: int = 8
    min_match_ratio: float = 0.40  # how much of the query tokens must appear in desc to count as "strict"

    def fetch(self, terms: Sequence[str]) -> RetrievalBatch:
        facts: List[IngredientFact | None] = []
        warnings: List[str] = []
        q_terms: List[str] = []

        for raw in terms:
            term = (raw or "").strip()
            if not term:
                facts.append(None)
                continue

            q_terms.append(term)
            items = self.client.search_foods(
                term,
                page_size=self.page_size,
                data_types=RETRIEVER_DATA_TYPES,
            )

            if not items:
                warnings.append(f"No USDA match found for '{term}'")
                facts.append(None)
                continue

            best = self._select_food(term, self._tokenize(term), items) if USE_RERANK else items[0]
            fact = self._food_to_fact(term, best)

            if fact is None:
                # try a fallback if chosen item was unusable
                fallback = items[0] if best is not items[0] else (items[1] if len(items) > 1 else None)
                if fallback:
                    fact = self._food_to_fact(term, fallback)

            if fact is None:
                desc = (best.get("description") or "unknown").lower()
                warnings.append(f"USDA entry unusable for '{term}' (picked '{desc}')")

            facts.append(fact)

        return RetrievalBatch(query_terms=q_terms, facts=facts, warnings=warnings)

    # ----------------------------- helpers --------------------------------

    @staticmethod
    def _tokenize(text: str) -> Set[str]:
        parts = re.split(r"[^a-z0-9]+", text.lower())
        tokens: Set[str] = set()
        for part in parts:
            if not part:
                continue
            tokens.add(part)
            if len(part) > 3 and part.endswith("s"):
                tokens.add(part[:-1])
        return tokens

    @classmethod
    def _token_overlap(cls, term_tokens: Set[str], text: str) -> float:
        if not term_tokens:
            return 0.0
        desc_tokens = cls._tokenize(text)
        if not desc_tokens:
            return 0.0
        return len(term_tokens & desc_tokens) / max(1, len(term_tokens))

    def _food_score(self, term: str, term_tokens: Set[str], food: dict) -> float:
        data_type = (food.get("dataType") or "").lower()
        ds_bonus = 1.5 if data_type in _PREFERRED_DATASETS else 0.0

        desc = (food.get("description") or "").lower()
        overlap = self._token_overlap(term_tokens, desc)
        phrase_bonus = 0.8 if term.lower().strip() in desc else 0.0

        # nudge away from “egg white / yolk” if user asked simply for “egg”
        nudge = 0.0
        if "egg" in term_tokens and "white" not in term_tokens and "yolk" not in term_tokens:
            if "egg white" in desc or "egg yolk" in desc:
                nudge -= 1.2

        # nudge away from “pasta” when asking for plain “spinach”
        if "spinach" in term_tokens and "pasta" not in term_tokens and "pasta" in desc:
            nudge -= 2.0

        return (3.0 * overlap) + ds_bonus + phrase_bonus + nudge

    def _select_food(self, term: str, term_tokens: Set[str], foods: List[dict]) -> dict:
        scored: List[tuple[float, float, dict]] = []
        for f in foods:
            desc = f.get("description", "")
            score = self._food_score(term, term_tokens, f)
            match_ratio = self._token_overlap(term_tokens, desc)
            scored.append((score, match_ratio, f))

        if not scored:
            logger.debug("USDA: falling back to first result for %s (no scored candidates)", term)
            return foods[0]

        # prefer strict matches (enough tokens overlap), else best overall
        strict = [t for t in scored if t[1] >= self.min_match_ratio]
        pool = strict or scored
        pool.sort(key=lambda t: (t[1], t[0]), reverse=True)

        if not strict:
            logger.debug("USDA: low-confidence match for %s → %s", term, pool[0][2].get("description", "unknown"))
        return pool[0][2]

    def _food_to_fact(self, query: str, food: dict) -> IngredientFact | None:
        # Pull macro values (may be missing for some entries)
        nutrients = {n.get("nutrientId"): n for n in (food.get("foodNutrients") or []) if isinstance(n, dict)}
        values = {"calories": 0.0, "protein_g": 0.0, "carbs_g": 0.0, "fats_g": 0.0}

        for nutrient_id, key in _NUTRIENT_ID_MAP.items():
            node = nutrients.get(nutrient_id)
            if node is None:
                continue
            try:
                values[key] = float(node.get("value") or 0.0)
            except (TypeError, ValueError):
                values[key] = 0.0

        # Require non-zero kcal
        if values["calories"] <= 0:
            logger.debug("Skipping '%s' because USDA returned zero calories", query)
            return None

        # Normalize to per 100 g using servingSize if provided
        serving_size = float(food.get("servingSize") or 100.0)
        serving_unit = (food.get("servingSizeUnit") or "g").lower()
        if serving_unit not in {"g", "gram", "grams"} or serving_size <= 0:
            serving_size = 100.0
        scale = 100.0 / serving_size
        for k in values:
            values[k] *= scale

        # Sanity check kcal per gram unless it's clearly a fat/oil
        desc_lc = (food.get("description") or "").lower()
        looks_like_fat = any(tok in desc_lc for tok in _OIL_TOKENS)
        kcal_per_g = (values["calories"] / 100.0) if values["calories"] else 0.0
        if kcal_per_g > 6.5 and not looks_like_fat:
            logger.debug(
                "Rejecting '%s' (%s) due to implausible kcal/g=%.2f",
                query, food.get("description"), kcal_per_g
            )
            return None

        try:
            nutrition = NutritionBreakdown(
                serving_size_g=100.0,
                calories=values["calories"],
                protein_g=values["protein_g"],
                carbs_g=values["carbs_g"],
                fats_g=values["fats_g"],
            )
        except (TypeError, ValueError):
            logger.debug("Invalid nutrition for '%s': %s", query, food)
            return None

        summary_parts = [food.get("description", ""), food.get("foodCategory", "")]
        summary = "; ".join(p for p in summary_parts if p).strip() or "Nutrition facts"
        tags: List[str] = []
        if food.get("foodCategory"):
            tags.append(food["foodCategory"])
        if food.get("dataType"):
            tags.append(food["dataType"])

        return IngredientFact(
            canonical_name=(food.get("description") or query).lower(),
            source_id=f"fdc:{food.get('fdcId')}",
            summary=summary,
            nutrition=nutrition,
            tags=tags,
        )
