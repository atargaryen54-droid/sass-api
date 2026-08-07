from pydantic import BaseModel


class SummaryResponse(BaseModel):
    total_clients: int
    total_projects: int
    active_api_keys: int
    pending_invoices: int
    paid_invoices: int
    failed_payments: int
    revenue_this_month: float
    usage_events_today: int

