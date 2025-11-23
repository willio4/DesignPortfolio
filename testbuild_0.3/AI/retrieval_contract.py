# File purpose: File is used to define the data structures for ingredient facts
# that will be retrived from USDA API (calories, macros, etc.)
# Shared data contracts for retrieval-augmented prompts.
 

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Iterable, List, Optional

# Define dataclasses for nutrition facts
@dataclass(slots=True)
class NutritionBreakdown:
    """Macro/micro nutrients expressed per serving."""

    serving_size_g: float
    calories: float
    protein_g: float
    carbs_g: float
    fats_g: float
    micros: Dict[str, float] = field(default_factory=dict)

    def to_prompt_fragment(self) -> str:
        micros_text = ", ".join(f"{k}: {v}mg" for k, v in self.micros.items())
        return (
            f"{self.calories:.0f} kcal; P {self.protein_g:.1f} g; "
            f"C {self.carbs_g:.1f} g; F {self.fats_g:.1f} g; "
            f"serving={self.serving_size_g:.0f} g"
            + (f"; micros: {micros_text}" if micros_text else "")
        )

# Atomic record describing single retreived row (of ingredient facts), pulled 
@dataclass(slots=True)
class IngredientFact:
    
    # declare cononical shape of ingredient fact returned by the retriever
    canonical_name: str
    source_id: str
    summary: str
    nutrition: NutritionBreakdown
    confidence: float = 1.0
    tags: List[str] = field(default_factory=list)

    def to_prompt_fragment(self) -> str:
        tag_text = f" ({', '.join(self.tags)})" if self.tags else ""
        return (
            f"- {self.canonical_name}{tag_text}: {self.summary} "
            f"[{self.nutrition.to_prompt_fragment()}]"
        )

# groups IngredientFact instances for a recipe request
# helpers to append items and format properly for the prompt
@dataclass(slots=True)
class RetrievalBatch:

    query_terms: List[str]
    facts: List[IngredientFact] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)

    def extend(self, new_facts: Iterable[IngredientFact]) -> None:
        self.facts.extend(new_facts)

    def to_prompt_block(self, heading: str = "Supporting ingredient facts") -> str:
        if not self.facts:
            return ""
        fragments = "\n".join(fact.to_prompt_fragment() for fact in self.facts)
        return f"{heading}:\n{fragments}"

    def to_dict(self) -> Dict[str, object]:
        return {
            "query_terms": self.query_terms,
            "facts": [
                {
                    "canonical_name": fact.canonical_name,
                    "source_id": fact.source_id,
                    "summary": fact.summary,
                    "nutrition": fact.nutrition.__dict__,
                    "confidence": fact.confidence,
                    "tags": fact.tags,
                }
                for fact in self.facts
            ],
            "warnings": self.warnings,
        }
