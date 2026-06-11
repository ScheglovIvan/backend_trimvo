import logging
from datetime import datetime, timezone, timedelta

from fastapi import APIRouter, Depends, HTTPException, Header
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from uuid import UUID
from pydantic import BaseModel

from core.config import get_settings
from core.database import get_db
from core.dependencies import get_current_user
from models.apple_iap_transaction import AppleIAPTransaction
from models.gem_package import GemPackage
from models.gem_transaction import GemTransaction
from models.subscription_plan import SubscriptionPlan
from models.user import User
from schemas.apple_iap import (
    AppleNotificationRequest,
    AppleRestoreItem,
    AppleRestoreRequest,
    AppleRestoreResponse,
    AppleVerifyPurchaseRequest,
    AppleVerifyPurchaseResponse,
    AppleVerifySubscriptionRequest,
    AppleVerifySubscriptionResponse,
)
from services.apple_iap import decode_and_verify_jws, parse_transaction_payload
from services.gems import add_gems

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/v1/payments", tags=["payments"])

_settings = get_settings()


# ── Legacy internal webhook (kept for compatibility) ─────────────────────────

class WebhookPayload(BaseModel):
    user_id: UUID
    gems_amount: int
    product_id: str
    payment_id: str


@router.post("/webhook")
def payment_webhook(
    body: WebhookPayload,
    db: Session = Depends(get_db),
    x_signature: str = Header(None),
):
    existing = db.query(GemTransaction).filter(
        GemTransaction.reference_id == body.payment_id,
        GemTransaction.type == "purchase",
    ).first()
    if existing:
        return {"success": True, "duplicate": True}

    user = db.query(User).filter(User.id == body.user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    add_gems(
        db, user, body.gems_amount,
        tx_type="purchase",
        description=f"Purchase: {body.product_id}",
        reference_id=body.payment_id,
    )
    return {"success": True}


# ── Helpers ───────────────────────────────────────────────────────────────────

def _verify_and_parse(signed_transaction: str) -> dict:
    try:
        raw = decode_and_verify_jws(signed_transaction)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"Invalid Apple transaction: {e}")
    return parse_transaction_payload(raw)


def _check_bundle_id(tx: dict) -> None:
    expected = _settings.apple_bundle_id
    if expected and tx["bundle_id"] != expected:
        raise HTTPException(
            status_code=400,
            detail=f"Bundle ID mismatch: got {tx['bundle_id']}, expected {expected}",
        )


def _check_environment(tx: dict) -> None:
    if _settings.apple_sandbox and tx["environment"] == "Production":
        raise HTTPException(status_code=400, detail="Production receipt rejected in sandbox mode")
    if not _settings.apple_sandbox and tx["environment"] == "Sandbox":
        raise HTTPException(status_code=400, detail="Sandbox receipt rejected in production mode")


def _apply_subscription(db: Session, user: User, plan: SubscriptionPlan, tx: dict, grant_bonus: bool = True) -> None:
    expires = tx["expires_date"]
    if expires is None:
        if plan.period == "lifetime":
            expires = None
        elif plan.period == "monthly":
            expires = datetime.now(timezone.utc) + timedelta(days=31)
        else:
            expires = datetime.now(timezone.utc) + timedelta(days=366)

    user.subscription_status = plan.tier
    user.subscription_expires_at = expires

    if grant_bonus and plan.bonus_gems > 0:
        add_gems(
            db, user, plan.bonus_gems,
            tx_type="subscription_bonus",
            description=f"Subscription bonus: {plan.name}",
            reference_id=tx["transaction_id"],
        )


# ── Apple IAP: gem purchase ────────────────────────────────────────────────────

@router.post("/apple/verify-purchase", response_model=AppleVerifyPurchaseResponse)
def apple_verify_purchase(
    body: AppleVerifyPurchaseRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    tx = _verify_and_parse(body.signed_transaction)
    _check_bundle_id(tx)
    _check_environment(tx)

    if tx["in_app_ownership_type"] == "FAMILY_SHARED":
        raise HTTPException(status_code=400, detail="Family Shared purchases not supported for gems")

    existing = db.query(AppleIAPTransaction).filter(
        AppleIAPTransaction.transaction_id == tx["transaction_id"]
    ).first()
    if existing:
        gem_pkg = db.query(GemPackage).filter(
            GemPackage.apple_product_id == tx["product_id"]
        ).first()
        total_gems = (gem_pkg.gems_amount + gem_pkg.bonus_gems) if gem_pkg else 0
        return AppleVerifyPurchaseResponse(
            success=True,
            transaction_id=tx["transaction_id"],
            product_id=tx["product_id"],
            gems_added=0,
            new_balance=current_user.gems,
        )

    gem_pkg = db.query(GemPackage).filter(
        GemPackage.apple_product_id == tx["product_id"],
        GemPackage.is_active == True,
    ).first()
    if not gem_pkg:
        raise HTTPException(
            status_code=404,
            detail=f"Gem package not found for product_id: {tx['product_id']}",
        )

    total_gems = (gem_pkg.gems_amount + gem_pkg.bonus_gems) * tx["quantity"]

    add_gems(
        db, current_user, total_gems,
        tx_type="purchase",
        description=f"Apple IAP: {gem_pkg.label or gem_pkg.apple_product_id}",
        reference_id=tx["transaction_id"],
    )

    iap_record = AppleIAPTransaction(
        user_id=current_user.id,
        transaction_id=tx["transaction_id"],
        original_transaction_id=tx["original_transaction_id"] or tx["transaction_id"],
        product_id=tx["product_id"],
        purchase_type="gem_purchase",
        quantity=tx["quantity"],
        environment=tx["environment"],
        purchase_date=tx["purchase_date"],
        expires_date=None,
        status="processed",
    )
    db.add(iap_record)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        # Concurrent duplicate — idempotent response
        return AppleVerifyPurchaseResponse(
            success=True,
            transaction_id=tx["transaction_id"],
            product_id=tx["product_id"],
            gems_added=0,
            new_balance=current_user.gems,
        )

    logger.info(
        "Apple gem purchase: user=%s product=%s gems=%d tx=%s",
        current_user.id, tx["product_id"], total_gems, tx["transaction_id"],
    )

    return AppleVerifyPurchaseResponse(
        success=True,
        transaction_id=tx["transaction_id"],
        product_id=tx["product_id"],
        gems_added=total_gems,
        new_balance=current_user.gems,
    )


# ── Apple IAP: subscription purchase ──────────────────────────────────────────

@router.post("/apple/verify-subscription", response_model=AppleVerifySubscriptionResponse)
def apple_verify_subscription(
    body: AppleVerifySubscriptionRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    tx = _verify_and_parse(body.signed_transaction)
    _check_bundle_id(tx)
    _check_environment(tx)

    existing = db.query(AppleIAPTransaction).filter(
        AppleIAPTransaction.transaction_id == tx["transaction_id"]
    ).first()
    if existing:
        return AppleVerifySubscriptionResponse(
            success=True,
            transaction_id=tx["transaction_id"],
            product_id=tx["product_id"],
            subscription_status=current_user.subscription_status,
            expires_at=current_user.subscription_expires_at,
            bonus_gems_added=0,
        )

    plan = db.query(SubscriptionPlan).filter(
        SubscriptionPlan.apple_product_id == tx["product_id"],
        SubscriptionPlan.is_active == True,
    ).first()
    if not plan:
        raise HTTPException(
            status_code=404,
            detail=f"Subscription plan not found for product_id: {tx['product_id']}",
        )

    bonus_gems_added = plan.bonus_gems if plan.bonus_gems > 0 else 0
    _apply_subscription(db, current_user, plan, tx)

    iap_record = AppleIAPTransaction(
        user_id=current_user.id,
        transaction_id=tx["transaction_id"],
        original_transaction_id=tx["original_transaction_id"] or tx["transaction_id"],
        product_id=tx["product_id"],
        purchase_type="subscription",
        quantity=1,
        environment=tx["environment"],
        purchase_date=tx["purchase_date"],
        expires_date=tx["expires_date"],
        status="processed",
    )
    db.add(iap_record)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        return AppleVerifySubscriptionResponse(
            success=True,
            transaction_id=tx["transaction_id"],
            product_id=tx["product_id"],
            subscription_status=current_user.subscription_status,
            expires_at=current_user.subscription_expires_at,
            bonus_gems_added=0,
        )

    logger.info(
        "Apple subscription: user=%s product=%s tier=%s expires=%s tx=%s",
        current_user.id, tx["product_id"], plan.tier,
        current_user.subscription_expires_at, tx["transaction_id"],
    )

    return AppleVerifySubscriptionResponse(
        success=True,
        transaction_id=tx["transaction_id"],
        product_id=tx["product_id"],
        subscription_status=current_user.subscription_status,
        expires_at=current_user.subscription_expires_at,
        bonus_gems_added=bonus_gems_added,
    )


# ── Apple IAP: restore purchases ──────────────────────────────────────────────

@router.post("/apple/restore", response_model=AppleRestoreResponse)
def apple_restore_purchases(
    body: AppleRestoreRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    restored: list[AppleRestoreItem] = []

    for signed_tx in body.signed_transactions:
        try:
            tx = _verify_and_parse(signed_tx)
            _check_bundle_id(tx)
        except HTTPException as e:
            logger.warning("Restore: skipping invalid transaction: %s", e.detail)
            continue

        already = db.query(AppleIAPTransaction).filter(
            AppleIAPTransaction.transaction_id == tx["transaction_id"]
        ).first()

        if already:
            restored.append(AppleRestoreItem(
                transaction_id=tx["transaction_id"],
                product_id=tx["product_id"],
                purchase_type=already.purchase_type,
                already_processed=True,
            ))
            continue

        gem_pkg = db.query(GemPackage).filter(
            GemPackage.apple_product_id == tx["product_id"],
            GemPackage.is_active == True,
        ).first()
        plan = db.query(SubscriptionPlan).filter(
            SubscriptionPlan.apple_product_id == tx["product_id"],
            SubscriptionPlan.is_active == True,
        ).first()

        if gem_pkg:
            purchase_type = "gem_purchase"
            total_gems = (gem_pkg.gems_amount + gem_pkg.bonus_gems) * tx["quantity"]
            add_gems(
                db, current_user, total_gems,
                tx_type="purchase",
                description=f"Apple IAP restore: {gem_pkg.label or gem_pkg.apple_product_id}",
                reference_id=tx["transaction_id"],
            )
        elif plan:
            purchase_type = "subscription"
            expires = tx["expires_date"]
            if plan.period == "lifetime" or (expires and expires > datetime.now(timezone.utc)):
                _apply_subscription(db, current_user, plan, tx)
        else:
            logger.warning("Restore: unknown product_id %s — skipping", tx["product_id"])
            continue

        iap_record = AppleIAPTransaction(
            user_id=current_user.id,
            transaction_id=tx["transaction_id"],
            original_transaction_id=tx["original_transaction_id"] or tx["transaction_id"],
            product_id=tx["product_id"],
            purchase_type=purchase_type,
            quantity=tx["quantity"],
            environment=tx["environment"],
            purchase_date=tx["purchase_date"],
            expires_date=tx["expires_date"],
            status="processed",
        )
        db.add(iap_record)
        restored.append(AppleRestoreItem(
            transaction_id=tx["transaction_id"],
            product_id=tx["product_id"],
            purchase_type=purchase_type,
            already_processed=False,
        ))

    db.commit()
    return AppleRestoreResponse(restored=restored)


# ── Apple App Store Server Notifications V2 ───────────────────────────────────

@router.post("/apple/notifications")
def apple_notifications(body: AppleNotificationRequest, db: Session = Depends(get_db)):
    """
    Receives App Store Server Notifications V2 from Apple.
    Handles subscription lifecycle events.
    Always returns 200 — Apple retries on non-2xx responses.
    """
    try:
        notification = decode_and_verify_jws(body.signedPayload)
    except ValueError as e:
        logger.error("Apple notification: invalid JWS: %s", e)
        return {"received": True}

    notification_type: str = notification.get("notificationType", "")
    subtype: str = notification.get("subtype", "") or ""
    data: dict = notification.get("data", {})

    signed_tx_jws: str = data.get("signedTransactionInfo", "")
    signed_renewal_jws: str = data.get("signedRenewalInfo", "")

    tx: dict = {}
    if signed_tx_jws:
        try:
            tx = parse_transaction_payload(decode_and_verify_jws(signed_tx_jws))
        except ValueError as e:
            logger.error("Apple notification: invalid signedTransactionInfo: %s", e)
            return {"received": True}

    logger.info(
        "Apple notification: type=%s subtype=%s product=%s original_tx=%s",
        notification_type, subtype, tx.get("product_id"), tx.get("original_transaction_id"),
    )

    if notification_type == "SUBSCRIBED":
        _handle_subscription_activated(db, tx, grant_bonus=True)
    elif notification_type == "DID_RENEW":
        _handle_subscription_activated(db, tx, grant_bonus=False)
    elif notification_type in ("EXPIRED", "DID_FAIL_TO_RENEW", "GRACE_PERIOD_EXPIRED"):
        _handle_subscription_expired(db, tx)
    elif notification_type in ("REFUND", "REVOKE"):
        _handle_refund_or_revoke(db, tx, notification_type)

    return {"received": True}


def _handle_subscription_activated(db: Session, tx: dict, grant_bonus: bool = True) -> None:
    if not tx.get("original_transaction_id"):
        return

    existing = db.query(AppleIAPTransaction).filter(
        AppleIAPTransaction.original_transaction_id == tx["original_transaction_id"],
        AppleIAPTransaction.purchase_type == "subscription",
    ).order_by(AppleIAPTransaction.created_at.desc()).first()

    if not existing:
        logger.warning(
            "Apple notification SUBSCRIBED/DID_RENEW: no user found for original_tx=%s",
            tx["original_transaction_id"],
        )
        return

    user = db.query(User).filter(User.id == existing.user_id).first()
    if not user:
        return

    plan = db.query(SubscriptionPlan).filter(
        SubscriptionPlan.apple_product_id == tx["product_id"],
        SubscriptionPlan.is_active == True,
    ).first()
    if not plan:
        logger.warning("Apple notification: plan not found for product_id=%s", tx["product_id"])
        return

    already = db.query(AppleIAPTransaction).filter(
        AppleIAPTransaction.transaction_id == tx["transaction_id"]
    ).first()
    if already:
        return

    _apply_subscription(db, user, plan, tx, grant_bonus=grant_bonus)

    iap_record = AppleIAPTransaction(
        user_id=user.id,
        transaction_id=tx["transaction_id"],
        original_transaction_id=tx["original_transaction_id"],
        product_id=tx["product_id"],
        purchase_type="subscription",
        quantity=1,
        environment=tx["environment"],
        purchase_date=tx["purchase_date"],
        expires_date=tx["expires_date"],
        status="processed",
    )
    db.add(iap_record)
    db.commit()


def _handle_subscription_expired(db: Session, tx: dict) -> None:
    if not tx.get("original_transaction_id"):
        return

    existing = db.query(AppleIAPTransaction).filter(
        AppleIAPTransaction.original_transaction_id == tx["original_transaction_id"],
        AppleIAPTransaction.purchase_type == "subscription",
    ).order_by(AppleIAPTransaction.created_at.desc()).first()

    if not existing:
        return

    user = db.query(User).filter(User.id == existing.user_id).first()
    if not user:
        return

    user.subscription_status = "free"
    user.subscription_expires_at = None

    db.query(AppleIAPTransaction).filter(
        AppleIAPTransaction.original_transaction_id == tx["original_transaction_id"],
        AppleIAPTransaction.status == "processed",
    ).update({"status": "expired"})

    db.commit()
    logger.info("Apple subscription expired: user=%s", user.id)


def _handle_refund_or_revoke(db: Session, tx: dict, notification_type: str) -> None:
    if not tx.get("transaction_id"):
        return

    iap_record = db.query(AppleIAPTransaction).filter(
        AppleIAPTransaction.transaction_id == tx["transaction_id"]
    ).first()
    if not iap_record or iap_record.status in ("refunded", "revoked"):
        return

    user = db.query(User).filter(User.id == iap_record.user_id).first()
    if not user:
        return

    new_status = "refunded" if notification_type == "REFUND" else "revoked"
    iap_record.status = new_status

    if iap_record.purchase_type == "subscription":
        user.subscription_status = "free"
        user.subscription_expires_at = None
    elif iap_record.purchase_type == "gem_purchase":
        gem_pkg = db.query(GemPackage).filter(
            GemPackage.apple_product_id == iap_record.product_id
        ).first()
        if gem_pkg:
            gems_to_deduct = (gem_pkg.gems_amount + gem_pkg.bonus_gems) * iap_record.quantity
            gems_to_deduct = min(gems_to_deduct, user.gems)
            if gems_to_deduct > 0:
                user.gems -= gems_to_deduct
                db.add(GemTransaction(
                    user_id=user.id,
                    amount=-gems_to_deduct,
                    balance_after=user.gems,
                    type="refund",
                    description=f"Apple {new_status}: {iap_record.product_id}",
                    reference_id=tx["transaction_id"],
                ))

    db.commit()
    logger.info(
        "Apple %s: user=%s tx=%s",
        notification_type.lower(), user.id, tx["transaction_id"],
    )
