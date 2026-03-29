from pydantic import BaseModel


class PricingRuleCreate(BaseModel):
    project_id: int
    event_type: str
    price_per_unit: float


class PricingRuleResponse(BaseModel):
    id: int
    project_id: int
    event_type: str
    price_per_unit: float

    class Config:
        from_attributes = True


class PricingSummary(BaseModel):
    event_type: str
    price_per_unit: float

    class Config:
        from_attributes = True
