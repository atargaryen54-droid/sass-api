from fastapi import APIRouter, Request, HTTPException, Depends
from app.api.deps import get_db
from app.payment.provider_factory import PaymentProviderFactory
from app.schemas.enums import PaymentProvider
from app.services.webhook_service import WebhookService
from sqlalchemy.orm import Session


router = APIRouter(prefix="/webhooks", tags=["Webhooks"])


@router.post("/stripe")
async def stripe_webhook(request: Request,  db: Session = Depends(get_db)):
    payload = await request.body()
    signature = request.headers.get("stripe-signature")

    provider = PaymentProviderFactory.get(
        PaymentProvider.STRIPE
    )

    try:
        event = provider.verify_webhook_signature(
            payload,
            signature,
        )
    except Exception:

        raise HTTPException(
            status_code=400,
            detail="Invalid webhook signature.",
        )
    
    print(f"Webhook received: {event['type']}")

    WebhookService.process_stripe_event(db=db, event=event)

    return {"received": True}

