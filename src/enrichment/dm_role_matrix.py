from __future__ import annotations

ROLE_MATRIX = {
    "shopify_commerce_agency": [
        "founder", "co-founder", "ceo", "head of ecommerce", "head of e-commerce", "cto", "growth lead",
    ],
    "pim_mdm_integrator": [
        "cto", "head of delivery", "solution architect", "solutions architect", "managing partner",
    ],
    "pl_cee_de_smb_agency": [
        "owner", "ceo", "managing director", "head of client services",
    ],
}

ROLE_WEIGHTS = {
    "founder": 1.00, "co-founder": 1.00, "owner": 1.00, "managing partner": 1.00,
    "ceo": 0.95, "cto": 0.90, "head of ecommerce": 0.90, "head of e-commerce": 0.90,
    "head of delivery": 0.90, "solution architect": 0.90, "solutions architect": 0.90,
    "managing director": 0.90, "head of client services": 0.85, "growth lead": 0.80,
}


def normalize_role(value: str | None) -> str:
    return " ".join((value or "").strip().lower().replace("–", "-").split())


def role_match_score(segment: str, role: str | None) -> float:
    norm = normalize_role(role)
    if not norm:
        return 0.0
    allowed = ROLE_MATRIX.get(segment, [])
    for target in allowed:
        if target in norm:
            return ROLE_WEIGHTS.get(target, 0.75)
    return 0.0
