# File to "normalize" the ingredient entries that are being returned by the model
# i.e, fix the formatting of quantities, measurements, etc. 

from fractions import Fraction
import math
import re
from typing import Any, Dict, List, Optional

# conservative defaults for countable items when no quantity is present
_DEFAULT_COUNT_QTY = {
    'egg': 1,
    'eggs': 1,
    'onion': 1,
    'shallot': 1,
    'tomato': 2,
    'tomatoes': 2,
    'lemon': 1,
    'avocado': 1,
    'clove': 1,
}


def infer_quantity_from_name(name: str) -> Optional[float]:
    """Try a conservative inference for countable ingredients (returns a float or None)."""
    if not name:
        return None
    low = name.lower()
    # match whole words
    for key, val in _DEFAULT_COUNT_QTY.items():
        if re.search(rf"\b{re.escape(key)}\b", low):
            return float(val)
    return None

# convert float quanitities to fraction form
def format_fraction(qty: Optional[float], max_denominator: int = 8) -> Optional[str]:
    """Return a human-friendly fraction string for qty (e.g., 1.5 -> '1 1/2')."""
    if qty is None:
        return None
    try:
        q = float(qty)
    except Exception:
        return None
    if math.isclose(q, round(q)):
        return str(int(round(q)))
    frac = Fraction(q).limit_denominator(max_denominator)
    num, den = frac.numerator, frac.denominator
    if num >= den:
        whole = num // den
        rem = num - whole * den
        if rem == 0:
            return str(whole)
        return f"{whole} {rem}/{den}"
    return f"{num}/{den}"

# regex used to parse the ingredient strings
# pattern to match 
_ING_RE = re.compile(
    r"(?P<qty>(?:\d+\s+\d+/\d+|\d+/\d+|\d+\.\d+|\d+))\s*(?P<unit>[a-zA-Z]+)?\s*(?P<name>[^\(]+)\s*(?:\((?P<kcal>\d+)\s*kcal\))?"
)

# This
def normalize_ingredient(ing: Any) -> Dict[str, Any]:
    """Normalize an ingredient entry (dict or free-text) into a dict with
    fields: name, quantity, quantity_display, unit, estimated_calories, note
    """
    if isinstance(ing, dict):
        qty = ing.get("quantity")
        qty_display = ing.get("quantity_display") or (format_fraction(qty) if qty is not None else None)
        return {
            "name": ing.get("name") or "",
            "quantity": qty,
            "quantity_display": qty_display,
            "unit": ing.get("unit") or "",
            "estimated_calories": ing.get("estimated_calories"),
            "note": ing.get("note"),
        }

    s = str(ing).strip()
    raw_s = s

    # Pre-clean common separators and malformed patterns produced by copy/paste or model output.
    # Normalize dashes to spaces and remove strange "— /2" patterns.
    s = s.replace('\u2014', ' ').replace('\u2013', ' ').replace('—', ' ').replace('–', ' ')
    s = re.sub(r"\s+", " ", s).strip()

    # Convert patterns like '1 - /2' or '1 — /2' to '1 1/2'
    s = re.sub(r"(?P<whole>\d+)\s*[–—\-]\s*/\s*(?P<den>\d+)", lambda m: f"{m.group('whole')} 1/{m.group('den')}", s)

    # If string starts with a dash/emdash, drop it (e.g., '— Salt and pepper')
    s = re.sub(r"^[–—\-]\s*", "", s)

    m = _ING_RE.match(s)
    if m:
        raw_qty = m.group("qty")
        qty = None
        if raw_qty:
            # parse integers, decimals, fractions, mixed numbers like '1 1/2'
            def parse_qty(qstr: str) -> Optional[float]:
                qstr = qstr.strip()
                try:
                    if " " in qstr and "/" in qstr:
                        # mixed number: '1 1/2'
                        whole, frac = qstr.split()
                        num, den = frac.split("/")
                        return float(whole) + float(num) / float(den)
                    if "/" in qstr:
                        num, den = qstr.split("/")
                        return float(num) / float(den)
                    return float(qstr)
                except Exception:
                    return None

            qty = parse_qty(raw_qty)

        unit = m.group("unit") or ""
        name = (m.group("name") or "").strip()
        # sanitize name: remove long dashes and stray punctuation that may remain
        name = re.sub(r'[–—-]+', ' ', name)
        name = re.sub(r'[:"\(\)]+', '', name).strip()
        kcal = int(m.group("kcal")) if m.group("kcal") else None
        # if no explicit qty, try to infer a conservative default
        if qty is None:
            inferred = infer_quantity_from_name(name)
            if inferred is not None:
                qty = inferred
        return {
            "name": name,
            "quantity": qty,
            "quantity_display": format_fraction(qty) if qty is not None else None,
            "unit": unit,
            "estimated_calories": kcal,
            "note": None,
            "raw": raw_s,
        }
    # fallback: try to extract any leading quantity/fraction more permissively
    fallback_qty_re = re.compile(r"(?P<qty>(?:\d+\s+\d+/\d+|\d+/\d+|\d+\.\d+|\d+))")
    m2 = fallback_qty_re.search(s)
    if m2:
        qty_raw = m2.group("qty")
        qty = None
        try:
            qty = None
            if " " in qty_raw and "/" in qty_raw:
                whole, frac = qty_raw.split()
                num, den = frac.split("/")
                qty = float(whole) + float(num) / float(den)
            elif "/" in qty_raw:
                num, den = qty_raw.split("/")
                qty = float(num) / float(den)
            else:
                qty = float(qty_raw)
        except Exception:
            qty = None

        # remove the qty token from the name and any leftover separators
        name_guess = re.sub(re.escape(qty_raw), "", s, count=1).strip()
        name_guess = re.sub(r'^[–—:\-\s]+', '', name_guess)
        name_guess = re.sub(r'[–—-]+', ' ', name_guess)
        name_guess = re.sub(r'[:"\(\)]+', '', name_guess).strip()
        # try to capture a unit as the first word of the remaining name
        parts = name_guess.split(None, 1)
        unit_guess = parts[0] if parts else ""
        if len(parts) > 1:
            name_guess = parts[1]

        # if no parsed qty, try to infer from name
        if qty is None:
            inferred = infer_quantity_from_name(name_guess)
            if inferred is not None:
                qty = inferred
        return {
            "name": name_guess,
            "quantity": qty,
            "quantity_display": format_fraction(qty) if qty is not None else None,
            "unit": unit_guess,
            "estimated_calories": None,
            "note": None,
            "raw": raw_s,
        }

    # final fallback: sanitize the raw string before returning
    s_clean = re.sub(r'[–—-]+', ' ', s)
    s_clean = re.sub(r'[:"\(\)]+', '', s_clean).strip()
    return {"name": s_clean, "quantity": None, "quantity_display": None, "unit": "", "estimated_calories": None, "note": None, "raw": raw_s}


def normalize_meals(meals: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Normalize the ingredients and instructions for each meal in-place and return the list.
    - ingredients will be a list of normalized ingredient dicts
    - instructions: if a string with multiple lines will be converted to a list; otherwise left as-is
    """
    def _strip_leading_numbering(s: str) -> str:
        """Remove common leading numbering or list markers from an instruction line.

        Examples removed: "1.", "1)", "1 -", "1:", "1 - Step" etc.
        """
        if not s:
            return s
        # remove leading whitespace then common numbering tokens like '1.', '1)', '1 -', '1:'
        s2 = re.sub(r"^\s*\d+\s*[\.):\-]+\s*", "", s)
        # also handle cases like '1. Step:' or '1) Step -'
        s2 = re.sub(r"^\s*\d+\s+[-–—:]\s*", "", s2)
        return s2.strip()

    for meal in meals:
        ing_list = meal.get("ingredients", []) or []
        meal["ingredients"] = [normalize_ingredient(i) for i in ing_list]

        instr = meal.get("instructions")
        # if instructions are a single string, split into lines and clean them
        if isinstance(instr, str):
            lines = [ln.strip() for ln in instr.splitlines() if ln.strip()]
            # strip leading numbering markers from each line
            cleaned = [_strip_leading_numbering(ln) for ln in lines]
            meal["instructions"] = cleaned if len(cleaned) > 1 else cleaned[0] if cleaned else instr
        # if instructions are a list, ensure we clean each element
        elif isinstance(instr, list):
            meal["instructions"] = [_strip_leading_numbering(str(ln)) for ln in instr]

    return meals
