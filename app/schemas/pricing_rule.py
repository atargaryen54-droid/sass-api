from pydantic import BaseModel, ConfigDict


from pydantic import BaseModel, ConfigDict


class PricingRuleCreate(BaseModel):
    event_type_external_id: str
    price_per_unit: float


class PricingRuleUpdate(BaseModel):
    price_per_unit: float | None = None


class PricingRuleResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    external_id: str
    event_code: str
    price_per_unit: float


class PricingRulesByProject(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    project_external_id: str
    project_name: str
    event_code: str
    pricing_rule: PricingRuleResponse


class PricingSummary(BaseModel):
    event_type: str
    price_per_unit: float

    class Config:
        from_attributes = True
