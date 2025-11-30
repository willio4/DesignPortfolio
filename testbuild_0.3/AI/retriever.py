# Takes normalized ingredient terms and returns the RetrievalBatch shape
# from retrieval_contract.py
# Currently implemented stub retriever for local testing, excluding USDA
# hookup for now

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import List, Protocol, Sequence

from .retrieval_contract import IngredientFact, NutritionBreakdown, RetrievalBatch
from .usda_client import USDAFoodDataClient

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


_NUTRIENT_ID_MAP = {
	1008: "calories",
	1003: "protein_g",
	1005: "carbs_g",
	1004: "fats_g",
}


logger = logging.getLogger(__name__)


@dataclass(slots=True)
class USDAIngredientRetriever:
	"""Fetch ingredient facts from USDA FoodData Central."""

	client: USDAFoodDataClient
	page_size: int = 3

	def fetch(self, ingredient_names: Sequence[str]) -> RetrievalBatch:
		normalized = [name.strip().lower() for name in ingredient_names if name and name.strip()]
		facts: List[IngredientFact] = []
		batch = RetrievalBatch(query_terms=list(normalized))

		for term in normalized:
			foods = self.client.search_foods(term, page_size=self.page_size)
			if not foods:
				batch.warnings.append(f"USDA: no data found for '{term}'")
				continue

			food = self._select_food(foods)
			fact = self._food_to_fact(term, food)
			if fact:
				facts.append(fact)
			else:
				batch.warnings.append(f"USDA: unable to parse nutrition for '{term}'")

		batch.extend(facts)
		return batch

	def _select_food(self, foods: List[dict]) -> dict:
		preferred_order = ("Foundation", "SR Legacy", "Survey (FNDDS)")
		for dtype in preferred_order:
			for food in foods:
				if food.get("dataType") == dtype:
					return food
		return foods[0]

	def _food_to_fact(self, query: str, food: dict) -> IngredientFact | None:
		nutrients = {
			n.get("nutrientId"): n for n in food.get("foodNutrients", []) if isinstance(n, dict)
		}
		values = {"calories": 0.0, "protein_g": 0.0, "carbs_g": 0.0, "fats_g": 0.0}

		for nutrient_id, key in _NUTRIENT_ID_MAP.items():
			node = nutrients.get(nutrient_id)
			if not node:
				continue
			try:
				values[key] = float(node.get("value") or 0)
			except (TypeError, ValueError):
				values[key] = 0.0

		serving_size = food.get("servingSize") or 100.0
		serving_unit = (food.get("servingSizeUnit") or "g").lower()
		if serving_unit not in {"g", "gram", "grams"}:
			serving_size = 100.0

		try:
			nutrition = NutritionBreakdown(
				serving_size_g=float(serving_size),
				calories=values["calories"],
				protein_g=values["protein_g"],
				carbs_g=values["carbs_g"],
				fats_g=values["fats_g"],
			)
		except (TypeError, ValueError):
			logger.debug("Invalid nutrition for %s: %s", query, food)
			return None

		summary_parts = [food.get("description", ""), food.get("foodCategory", "")]
		summary = "; ".join(part for part in summary_parts if part).strip() or "Nutrition facts"
		tags: List[str] = []
		if food.get("foodCategory"):
			tags.append(food["foodCategory"])
		if food.get("dataType"):
			tags.append(food["dataType"])

		return IngredientFact(
			canonical_name=food.get("description", query).lower(),
			source_id=f"fdc:{food.get('fdcId')}",
			summary=summary,
			nutrition=nutrition,
			tags=tags,
		)
