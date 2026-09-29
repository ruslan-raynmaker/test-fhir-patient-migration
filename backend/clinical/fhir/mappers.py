from datetime import date, datetime, timezone

LOINC = "http://loinc.org"
GENDERS = {"male", "female", "other", "unknown"}


def map_patient(resource):
    name = _pick_name(resource.get("name") or [])
    given = " ".join(name.get("given") or [])
    family = name.get("family") or ""
    if not given and not family:
        given = name.get("text") or ""

    gender = resource.get("gender") or ""
    return {
        "fhir_id": resource["id"],
        "given_name": _clip(given),
        "family_name": _clip(family),
        "gender": gender if gender in GENDERS else "",
        "birth_date": parse_date(resource.get("birthDate")),
        "source_updated_at": parse_datetime((resource.get("meta") or {}).get("lastUpdated")),
    }


def map_observation(resource):
    code = resource.get("code") or {}
    coding = _pick_coding(code.get("coding") or [])
    category = _pick_coding(_first(resource.get("category")).get("coding") or [])

    return {
        "fhir_id": resource["id"],
        "status": resource.get("status") or "",
        "category": _clip(category.get("code") or "", 64),
        "code": _clip(coding.get("code") or "", 64),
        "code_system": _clip(coding.get("system") or ""),
        "display": _clip(coding.get("display") or code.get("text") or ""),
        "effective_at": _effective_at(resource),
        "components": [_map_component(c) for c in resource.get("component") or []],
        **_map_value(resource),
    }


def _map_component(component):
    code = component.get("code") or {}
    coding = _pick_coding(code.get("coding") or [])
    value = _map_value(component)
    return {
        "code": coding.get("code") or "",
        "display": coding.get("display") or code.get("text") or "",
        "value": value["value_number"] if value["value_number"] is not None else value["value_text"],
        "unit": value["value_unit"],
    }


def _map_value(resource):
    number, unit, text = None, "", ""

    if "valueQuantity" in resource:
        quantity = resource["valueQuantity"] or {}
        number = _to_float(quantity.get("value"))
        unit = quantity.get("unit") or quantity.get("code") or ""
    elif "valueInteger" in resource:
        number = _to_float(resource["valueInteger"])
    elif "valueCodeableConcept" in resource:
        concept = resource["valueCodeableConcept"] or {}
        coding = _first(concept.get("coding"))
        text = concept.get("text") or coding.get("display") or coding.get("code") or ""
    elif "valueString" in resource:
        text = resource["valueString"] or ""
    elif "valueBoolean" in resource:
        text = "true" if resource["valueBoolean"] else "false"
    elif "valueDateTime" in resource:
        text = resource["valueDateTime"] or ""

    return {"value_number": number, "value_unit": _clip(unit, 64), "value_text": _clip(text)}


def _effective_at(resource):
    period = resource.get("effectivePeriod") or {}
    raw = (
        resource.get("effectiveDateTime")
        or resource.get("effectiveInstant")
        or period.get("start")
        or resource.get("issued")
    )
    return parse_datetime(raw)


def _pick_name(names):
    for use in ("official", "usual"):
        for name in names:
            if name.get("use") == use:
                return name
    return _first(names)


def _pick_coding(codings):
    for coding in codings:
        if coding.get("system") == LOINC:
            return coding
    return _first(codings)


def _first(items):
    return items[0] if items else {}


def _clip(value, length=255):
    return str(value)[:length]


def _to_float(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def parse_date(value):
    try:
        return date.fromisoformat(value)
    except (TypeError, ValueError):
        return None


def parse_datetime(value):
    if not isinstance(value, str) or not value:
        return None
    if len(value) == 4:
        value += "-01-01"
    elif len(value) == 7:
        value += "-01"
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed
