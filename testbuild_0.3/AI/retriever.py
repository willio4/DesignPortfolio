# Takes normalized ingredient terms and returns the RetrievalBatch shape
# from retrieval_contract.py
# Currently implemented stub retriever for local testing, excluding USDA
# hookup for now

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Protocol, Sequence

from .retrieval_contract import IngredientFact, NutritionBreakdown, RetrievalBatch

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
