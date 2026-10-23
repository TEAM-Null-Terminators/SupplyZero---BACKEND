from enum import StrEnum


class ProductCategory(StrEnum):
    PHARMA = "PHARMA"
    PRODUCE = "PRODUCE"
    DAIRY = "DAIRY"
    BIOLOGIC = "BIOLOGIC"


class ModelType(StrEnum):
    ARRHENIUS = "ARRHENIUS"
    Q10 = "Q10"


class Health(StrEnum):
    GREEN = "GREEN"
    AMBER = "AMBER"
    RED = "RED"


class Action(StrEnum):
    CONTINUE = "CONTINUE"
    REROUTE = "REROUTE"
    CLEARANCE = "CLEARANCE"
    QUARANTINE = "QUARANTINE"


class RecommendationStatus(StrEnum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    AUTO_EXECUTED = "AUTO_EXECUTED"
