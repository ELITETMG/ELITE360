from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func, desc
from datetime import datetime
import uuid
from app.db.session import get_db
from app.core.auth import get_current_user
from app.models.models import (User, Invoice, InvoiceLineItem, InvoiceStatus,
    RateCard, Payment, ChangeOrder, Task, Project, OrgMember, TaskStatus)

router = APIRouter(prefix="/api/billing", tags=["billing"])


def recalculate_invoice(invoice, db: Session):
    subtotal = db.query(func.coalesce(func.sum(InvoiceLineItem.total_amount), 0)).filter(
        InvoiceLineItem.invoice_id == invoice.id
    ).scalar()
    invoice.subtotal = float(subtotal)
    invoice.tax_amount = invoice.subtotal * (invoice.tax_rate or 0) / 100
    invoice.retainage_amount = invoice.subtotal * (invoice.retainage_pct or 0) / 100
    invoice.total_amount = invoice.subtotal + invoice.tax_amount - (invoice.discount_amount or 0) - invoice.retainage_amount
    invoice.balance_due = invoice.total_amount - (invoice.amount_paid or 0)
    db.commit()


def _get_user_org(user: User, db: Session):
    membership = db.query(OrgMember).filter(OrgMember.user_id == user.id).first()
    if not membership:
        raise HTTPException(status_code=400, detail="User has no organization")
    return membership.org_id


def _get_invoice_or_404(invoice_id: str, org_id: str, db: Session):
    invoice = db.query(Invoice).filter(Invoice.id == invoice_id, Invoice.org_id == org_id).first()
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")
    return invoice


@router.get("/invoices")
def list_invoices(
    project_id: str = Query(None),
    status: str = Query(None),
    limit: int = Query(50),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    org_id = _get_user_org(current_user, db)
    q = db.query(Invoice).filter(Invoice.org_id == org_id)
    if project_id:
        q = q.filter(Invoice.project_id == project_id)
    if status:
        q = q.filter(Invoice.status == status)
    q = q.order_by(desc(Invoice.created_at)).limit(limit)
    invoices = q.all()
    return [{
        "id": inv.id,
        "invoice_number": inv.invoice_number,
        "title": inv.title,
        "project_id": inv.project_id,
        "status": inv.status.value if inv.status else None,
        "subtotal": inv.subtotal,
        "tax_amount": inv.tax_amount,
        "discount_amount": inv.discount_amount,
        "total_amount": inv.total_amount,
        "amount_paid": inv.amount_paid,
        "balance_due": inv.balance_due,
        "due_date": inv.due_date.isoformat() if inv.due_date else None,
        "billing_period_start": inv.billing_period_start.isoformat() if inv.billing_period_start else None,
        "billing_period_end": inv.billing_period_end.isoformat() if inv.billing_period_end else None,
        "submitted_at": inv.submitted_at.isoformat() if inv.submitted_at else None,
        "created_at": inv.created_at.isoformat() if inv.created_at else None,
        "line_item_count": len(inv.line_items) if inv.line_items else 0
    } for inv in invoices]


@router.post("/invoices")
def create_invoice(
    data: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    org_id = _get_user_org(current_user, db)
    project = db.query(Project).filter(Project.id == data.get("project_id")).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    if project.owner_org_id != org_id and project.executing_org_id != org_id:
        raise HTTPException(status_code=403, detail="Project does not belong to your organization")

    today = datetime.utcnow().strftime("%Y%m%d")
    count = db.query(Invoice).filter(
        Invoice.invoice_number.like(f"INV-{today}-%")
    ).count()
    invoice_number = f"INV-{today}-{count + 1:04d}"

    invoice = Invoice(
        id=str(uuid.uuid4()),
        project_id=data["project_id"],
        org_id=org_id,
        invoice_number=invoice_number,
        title=data.get("title", ""),
        description=data.get("description"),
        billing_period_start=datetime.fromisoformat(data["billing_period_start"]) if data.get("billing_period_start") else None,
        billing_period_end=datetime.fromisoformat(data["billing_period_end"]) if data.get("billing_period_end") else None,
        due_date=datetime.fromisoformat(data["due_date"]) if data.get("due_date") else None,
        tax_rate=data.get("tax_rate", 0),
        retainage_pct=data.get("retainage_pct", 0),
        terms=data.get("terms"),
        notes=data.get("notes"),
        created_by=current_user.id,
        status=InvoiceStatus.DRAFT
    )
    db.add(invoice)
    db.commit()
    db.refresh(invoice)
    return {
        "id": invoice.id,
        "invoice_number": invoice.invoice_number,
        "title": invoice.title,
        "status": invoice.status.value,
        "created_at": invoice.created_at.isoformat() if invoice.created_at else None
    }


@router.get("/invoices/{invoice_id}")
def get_invoice(
    invoice_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    org_id = _get_user_org(current_user, db)
    invoice = db.query(Invoice).options(
        joinedload(Invoice.line_items),
        joinedload(Invoice.payments),
        joinedload(Invoice.project),
        joinedload(Invoice.creator)
    ).filter(Invoice.id == invoice_id, Invoice.org_id == org_id).first()
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")

    return {
        "id": invoice.id,
        "invoice_number": invoice.invoice_number,
        "title": invoice.title,
        "description": invoice.description,
        "project_id": invoice.project_id,
        "project_name": invoice.project.name if invoice.project else None,
        "org_id": invoice.org_id,
        "status": invoice.status.value if invoice.status else None,
        "billing_period_start": invoice.billing_period_start.isoformat() if invoice.billing_period_start else None,
        "billing_period_end": invoice.billing_period_end.isoformat() if invoice.billing_period_end else None,
        "due_date": invoice.due_date.isoformat() if invoice.due_date else None,
        "subtotal": invoice.subtotal,
        "tax_rate": invoice.tax_rate,
        "tax_amount": invoice.tax_amount,
        "discount_amount": invoice.discount_amount,
        "total_amount": invoice.total_amount,
        "amount_paid": invoice.amount_paid,
        "balance_due": invoice.balance_due,
        "retainage_pct": invoice.retainage_pct,
        "retainage_amount": invoice.retainage_amount,
        "change_order_total": invoice.change_order_total,
        "terms": invoice.terms,
        "notes": invoice.notes,
        "submitted_at": invoice.submitted_at.isoformat() if invoice.submitted_at else None,
        "approved_at": invoice.approved_at.isoformat() if invoice.approved_at else None,
        "approved_by": invoice.approved_by,
        "created_by": invoice.created_by,
        "creator_name": invoice.creator.full_name if invoice.creator else None,
        "created_at": invoice.created_at.isoformat() if invoice.created_at else None,
        "line_items": [{
            "id": li.id,
            "line_number": li.line_number,
            "category": li.category,
            "description": li.description,
            "work_type": li.work_type,
            "unit": li.unit,
            "quantity": li.quantity,
            "unit_rate": li.unit_rate,
            "labor_cost": li.labor_cost,
            "material_cost": li.material_cost,
            "equipment_cost": li.equipment_cost,
            "permit_cost": li.permit_cost,
            "subcontractor_cost": li.subcontractor_cost,
            "other_cost": li.other_cost,
            "total_amount": li.total_amount,
            "is_change_order": li.is_change_order,
            "change_order_ref": li.change_order_ref,
            "notes": li.notes,
            "billable": li.billable,
            "work_date": li.work_date.isoformat() if li.work_date else None,
            "task_id": li.task_id,
            "rate_card_id": li.rate_card_id
        } for li in (invoice.line_items or [])],
        "payments": [{
            "id": p.id,
            "amount": p.amount,
            "payment_method": p.payment_method,
            "reference_number": p.reference_number,
            "payment_date": p.payment_date.isoformat() if p.payment_date else None,
            "notes": p.notes,
            "created_at": p.created_at.isoformat() if p.created_at else None
        } for p in (invoice.payments or [])]
    }


@router.put("/invoices/{invoice_id}")
def update_invoice(
    invoice_id: str,
    data: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    org_id = _get_user_org(current_user, db)
    invoice = _get_invoice_or_404(invoice_id, org_id, db)

    for field in ["title", "description", "terms", "notes"]:
        if field in data:
            setattr(invoice, field, data[field])

    if "due_date" in data:
        invoice.due_date = datetime.fromisoformat(data["due_date"]) if data["due_date"] else None
    if "tax_rate" in data:
        invoice.tax_rate = data["tax_rate"]
    if "discount_amount" in data:
        invoice.discount_amount = data["discount_amount"]
    if "retainage_pct" in data:
        invoice.retainage_pct = data["retainage_pct"]
    if "status" in data:
        invoice.status = data["status"]

    db.commit()
    recalculate_invoice(invoice, db)
    db.refresh(invoice)
    return {"id": invoice.id, "status": invoice.status.value if invoice.status else None, "total_amount": invoice.total_amount}


@router.delete("/invoices/{invoice_id}")
def delete_invoice(
    invoice_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    org_id = _get_user_org(current_user, db)
    invoice = _get_invoice_or_404(invoice_id, org_id, db)
    if invoice.status != InvoiceStatus.DRAFT:
        raise HTTPException(status_code=400, detail="Only draft invoices can be deleted")
    db.delete(invoice)
    db.commit()
    return {"message": "Invoice deleted"}


@router.post("/invoices/{invoice_id}/line-items")
def add_line_item(
    invoice_id: str,
    data: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    org_id = _get_user_org(current_user, db)
    invoice = _get_invoice_or_404(invoice_id, org_id, db)

    max_line = db.query(func.coalesce(func.max(InvoiceLineItem.line_number), 0)).filter(
        InvoiceLineItem.invoice_id == invoice_id
    ).scalar()

    quantity = data.get("quantity", 0)
    unit_rate = data.get("unit_rate", 0)
    labor_cost = data.get("labor_cost", 0)
    material_cost = data.get("material_cost", 0)
    equipment_cost = data.get("equipment_cost", 0)
    permit_cost = data.get("permit_cost", 0)
    subcontractor_cost = data.get("subcontractor_cost", 0)
    other_cost = data.get("other_cost", 0)
    total_amount = (quantity * unit_rate) + labor_cost + material_cost + equipment_cost + permit_cost + subcontractor_cost + other_cost

    item = InvoiceLineItem(
        id=str(uuid.uuid4()),
        invoice_id=invoice_id,
        line_number=max_line + 1,
        category=data.get("category", "labor"),
        description=data.get("description", ""),
        work_type=data.get("work_type"),
        unit=data.get("unit", "each"),
        quantity=quantity,
        unit_rate=unit_rate,
        labor_cost=labor_cost,
        material_cost=material_cost,
        equipment_cost=equipment_cost,
        permit_cost=permit_cost,
        subcontractor_cost=subcontractor_cost,
        other_cost=other_cost,
        total_amount=total_amount,
        task_id=data.get("task_id"),
        rate_card_id=data.get("rate_card_id"),
        is_change_order=data.get("is_change_order", False),
        change_order_ref=data.get("change_order_ref"),
        notes=data.get("notes"),
        work_date=datetime.fromisoformat(data["work_date"]) if data.get("work_date") else None,
        billable=data.get("billable", True)
    )
    db.add(item)
    db.commit()
    recalculate_invoice(invoice, db)
    db.refresh(item)
    return {
        "id": item.id,
        "line_number": item.line_number,
        "description": item.description,
        "total_amount": item.total_amount,
        "invoice_total": invoice.total_amount
    }


@router.put("/invoices/{invoice_id}/line-items/{item_id}")
def update_line_item(
    invoice_id: str,
    item_id: str,
    data: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    org_id = _get_user_org(current_user, db)
    invoice = _get_invoice_or_404(invoice_id, org_id, db)
    item = db.query(InvoiceLineItem).filter(
        InvoiceLineItem.id == item_id, InvoiceLineItem.invoice_id == invoice_id
    ).first()
    if not item:
        raise HTTPException(status_code=404, detail="Line item not found")

    for field in ["category", "description", "work_type", "unit", "notes", "change_order_ref"]:
        if field in data:
            setattr(item, field, data[field])

    if "quantity" in data:
        item.quantity = data["quantity"]
    if "unit_rate" in data:
        item.unit_rate = data["unit_rate"]
    for cost_field in ["labor_cost", "material_cost", "equipment_cost", "permit_cost", "subcontractor_cost", "other_cost"]:
        if cost_field in data:
            setattr(item, cost_field, data[cost_field])
    if "task_id" in data:
        item.task_id = data["task_id"]
    if "rate_card_id" in data:
        item.rate_card_id = data["rate_card_id"]
    if "is_change_order" in data:
        item.is_change_order = data["is_change_order"]
    if "billable" in data:
        item.billable = data["billable"]
    if "work_date" in data:
        item.work_date = datetime.fromisoformat(data["work_date"]) if data["work_date"] else None

    item.total_amount = (item.quantity * item.unit_rate) + (item.labor_cost or 0) + (item.material_cost or 0) + \
        (item.equipment_cost or 0) + (item.permit_cost or 0) + (item.subcontractor_cost or 0) + (item.other_cost or 0)

    db.commit()
    recalculate_invoice(invoice, db)
    return {"id": item.id, "total_amount": item.total_amount, "invoice_total": invoice.total_amount}


@router.delete("/invoices/{invoice_id}/line-items/{item_id}")
def delete_line_item(
    invoice_id: str,
    item_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    org_id = _get_user_org(current_user, db)
    invoice = _get_invoice_or_404(invoice_id, org_id, db)
    item = db.query(InvoiceLineItem).filter(
        InvoiceLineItem.id == item_id, InvoiceLineItem.invoice_id == invoice_id
    ).first()
    if not item:
        raise HTTPException(status_code=404, detail="Line item not found")
    db.delete(item)
    db.commit()
    recalculate_invoice(invoice, db)
    return {"message": "Line item deleted", "invoice_total": invoice.total_amount}


@router.post("/invoices/{invoice_id}/submit")
def submit_invoice(
    invoice_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    org_id = _get_user_org(current_user, db)
    invoice = _get_invoice_or_404(invoice_id, org_id, db)
    if invoice.status != InvoiceStatus.DRAFT:
        raise HTTPException(status_code=400, detail="Only draft invoices can be submitted")
    invoice.status = InvoiceStatus.SUBMITTED
    invoice.submitted_at = datetime.utcnow()
    db.commit()
    return {"id": invoice.id, "status": invoice.status.value, "submitted_at": invoice.submitted_at.isoformat()}


@router.post("/invoices/{invoice_id}/approve")
def approve_invoice(
    invoice_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    org_id = _get_user_org(current_user, db)
    invoice = _get_invoice_or_404(invoice_id, org_id, db)
    if invoice.status != InvoiceStatus.SUBMITTED:
        raise HTTPException(status_code=400, detail="Only submitted invoices can be approved")
    invoice.status = InvoiceStatus.APPROVED
    invoice.approved_by = current_user.id
    invoice.approved_at = datetime.utcnow()
    db.commit()
    return {"id": invoice.id, "status": invoice.status.value, "approved_at": invoice.approved_at.isoformat()}


@router.post("/invoices/{invoice_id}/reject")
def reject_invoice(
    invoice_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    org_id = _get_user_org(current_user, db)
    invoice = _get_invoice_or_404(invoice_id, org_id, db)
    if invoice.status != InvoiceStatus.SUBMITTED:
        raise HTTPException(status_code=400, detail="Only submitted invoices can be rejected")
    invoice.status = InvoiceStatus.REJECTED
    db.commit()
    return {"id": invoice.id, "status": invoice.status.value}


@router.post("/invoices/{invoice_id}/payments")
def record_payment(
    invoice_id: str,
    data: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    org_id = _get_user_org(current_user, db)
    invoice = _get_invoice_or_404(invoice_id, org_id, db)

    amount = data.get("amount", 0)
    if amount <= 0:
        raise HTTPException(status_code=400, detail="Payment amount must be positive")

    payment = Payment(
        id=str(uuid.uuid4()),
        invoice_id=invoice_id,
        amount=amount,
        payment_method=data.get("payment_method"),
        reference_number=data.get("reference_number"),
        payment_date=datetime.fromisoformat(data["payment_date"]) if data.get("payment_date") else datetime.utcnow(),
        notes=data.get("notes"),
        recorded_by=current_user.id
    )
    db.add(payment)

    invoice.amount_paid = (invoice.amount_paid or 0) + amount
    invoice.balance_due = invoice.total_amount - invoice.amount_paid

    if invoice.balance_due <= 0:
        invoice.status = InvoiceStatus.PAID
        invoice.paid_at = datetime.utcnow()
    else:
        invoice.status = InvoiceStatus.PARTIALLY_PAID

    db.commit()
    db.refresh(payment)
    return {
        "id": payment.id,
        "amount": payment.amount,
        "invoice_amount_paid": invoice.amount_paid,
        "invoice_balance_due": invoice.balance_due,
        "invoice_status": invoice.status.value
    }


@router.get("/invoices/{invoice_id}/payments")
def list_payments(
    invoice_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    org_id = _get_user_org(current_user, db)
    _get_invoice_or_404(invoice_id, org_id, db)
    payments = db.query(Payment).filter(Payment.invoice_id == invoice_id).order_by(Payment.payment_date).all()
    return [{
        "id": p.id,
        "amount": p.amount,
        "payment_method": p.payment_method,
        "reference_number": p.reference_number,
        "payment_date": p.payment_date.isoformat() if p.payment_date else None,
        "notes": p.notes,
        "recorded_by": p.recorded_by,
        "created_at": p.created_at.isoformat() if p.created_at else None
    } for p in payments]


@router.post("/invoices/{invoice_id}/generate-from-tasks")
def generate_from_tasks(
    invoice_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    org_id = _get_user_org(current_user, db)
    invoice = _get_invoice_or_404(invoice_id, org_id, db)

    tasks = db.query(Task).filter(
        Task.project_id == invoice.project_id,
        Task.status.in_([TaskStatus.APPROVED, TaskStatus.BILLED])
    ).all()

    if not tasks:
        raise HTTPException(status_code=400, detail="No approved/billed tasks found for this project")

    max_line = db.query(func.coalesce(func.max(InvoiceLineItem.line_number), 0)).filter(
        InvoiceLineItem.invoice_id == invoice_id
    ).scalar()

    items_created = 0
    for task in tasks:
        max_line += 1
        quantity = task.actual_qty or 0
        unit_rate = task.unit_cost or 0
        total_amount = quantity * unit_rate

        item = InvoiceLineItem(
            id=str(uuid.uuid4()),
            invoice_id=invoice_id,
            task_id=task.id,
            line_number=max_line,
            category="labor",
            description=task.name,
            unit=task.unit or "each",
            quantity=quantity,
            unit_rate=unit_rate,
            total_amount=total_amount,
            billable=True
        )
        db.add(item)
        items_created += 1

    db.commit()
    recalculate_invoice(invoice, db)
    return {
        "message": f"Generated {items_created} line items from tasks",
        "items_created": items_created,
        "invoice_total": invoice.total_amount
    }


@router.get("/rate-cards")
def list_rate_cards(
    category: str = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    org_id = _get_user_org(current_user, db)
    q = db.query(RateCard).filter(RateCard.org_id == org_id, RateCard.is_active == True)
    if category:
        q = q.filter(RateCard.category == category)
    cards = q.order_by(RateCard.name).all()
    return [{
        "id": c.id,
        "name": c.name,
        "category": c.category,
        "description": c.description,
        "unit": c.unit,
        "unit_rate": c.unit_rate,
        "labor_rate": c.labor_rate,
        "material_rate": c.material_rate,
        "equipment_rate": c.equipment_rate,
        "permit_rate": c.permit_rate,
        "is_active": c.is_active,
        "effective_date": c.effective_date.isoformat() if c.effective_date else None,
        "expiry_date": c.expiry_date.isoformat() if c.expiry_date else None
    } for c in cards]


@router.post("/rate-cards")
def create_rate_card(
    data: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    org_id = _get_user_org(current_user, db)
    card = RateCard(
        id=str(uuid.uuid4()),
        org_id=org_id,
        name=data.get("name", ""),
        category=data.get("category", "labor"),
        description=data.get("description"),
        unit=data.get("unit", "each"),
        unit_rate=data.get("unit_rate", 0),
        labor_rate=data.get("labor_rate"),
        material_rate=data.get("material_rate"),
        equipment_rate=data.get("equipment_rate"),
        permit_rate=data.get("permit_rate"),
        effective_date=datetime.fromisoformat(data["effective_date"]) if data.get("effective_date") else None,
        expiry_date=datetime.fromisoformat(data["expiry_date"]) if data.get("expiry_date") else None
    )
    db.add(card)
    db.commit()
    db.refresh(card)
    return {"id": card.id, "name": card.name, "category": card.category, "unit_rate": card.unit_rate}


@router.put("/rate-cards/{card_id}")
def update_rate_card(
    card_id: str,
    data: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    org_id = _get_user_org(current_user, db)
    card = db.query(RateCard).filter(RateCard.id == card_id, RateCard.org_id == org_id).first()
    if not card:
        raise HTTPException(status_code=404, detail="Rate card not found")

    for field in ["name", "category", "description", "unit"]:
        if field in data:
            setattr(card, field, data[field])
    for num_field in ["unit_rate", "labor_rate", "material_rate", "equipment_rate", "permit_rate"]:
        if num_field in data:
            setattr(card, num_field, data[num_field])
    if "effective_date" in data:
        card.effective_date = datetime.fromisoformat(data["effective_date"]) if data["effective_date"] else None
    if "expiry_date" in data:
        card.expiry_date = datetime.fromisoformat(data["expiry_date"]) if data["expiry_date"] else None
    if "is_active" in data:
        card.is_active = data["is_active"]

    db.commit()
    return {"id": card.id, "name": card.name, "updated": True}


@router.delete("/rate-cards/{card_id}")
def deactivate_rate_card(
    card_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    org_id = _get_user_org(current_user, db)
    card = db.query(RateCard).filter(RateCard.id == card_id, RateCard.org_id == org_id).first()
    if not card:
        raise HTTPException(status_code=404, detail="Rate card not found")
    card.is_active = False
    db.commit()
    return {"message": "Rate card deactivated"}


@router.get("/change-orders")
def list_change_orders(
    project_id: str = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    org_id = _get_user_org(current_user, db)
    q = db.query(ChangeOrder).join(Project).filter(
        (Project.executing_org_id == org_id) | (Project.owner_org_id == org_id)
    )
    if project_id:
        q = q.filter(ChangeOrder.project_id == project_id)
    orders = q.order_by(desc(ChangeOrder.created_at)).all()
    return [{
        "id": co.id,
        "project_id": co.project_id,
        "co_number": co.co_number,
        "title": co.title,
        "description": co.description,
        "reason": co.reason,
        "status": co.status,
        "amount": co.amount,
        "labor_amount": co.labor_amount,
        "material_amount": co.material_amount,
        "equipment_amount": co.equipment_amount,
        "requested_by": co.requested_by,
        "approved_by": co.approved_by,
        "approved_at": co.approved_at.isoformat() if co.approved_at else None,
        "created_at": co.created_at.isoformat() if co.created_at else None
    } for co in orders]


@router.post("/change-orders")
def create_change_order(
    data: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    project = db.query(Project).filter(Project.id == data.get("project_id")).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    count = db.query(ChangeOrder).filter(ChangeOrder.project_id == data["project_id"]).count()
    co_number = f"CO-{count + 1:04d}"

    co = ChangeOrder(
        id=str(uuid.uuid4()),
        project_id=data["project_id"],
        co_number=co_number,
        title=data.get("title", ""),
        description=data.get("description"),
        reason=data.get("reason"),
        amount=data.get("amount", 0),
        labor_amount=data.get("labor_amount", 0),
        material_amount=data.get("material_amount", 0),
        equipment_amount=data.get("equipment_amount", 0),
        requested_by=current_user.id
    )
    db.add(co)
    db.commit()
    db.refresh(co)
    return {"id": co.id, "co_number": co.co_number, "title": co.title, "status": co.status}


@router.put("/change-orders/{co_id}/approve")
def approve_change_order(
    co_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    co = db.query(ChangeOrder).filter(ChangeOrder.id == co_id).first()
    if not co:
        raise HTTPException(status_code=404, detail="Change order not found")
    if co.status != "pending":
        raise HTTPException(status_code=400, detail="Only pending change orders can be approved")
    co.status = "approved"
    co.approved_by = current_user.id
    co.approved_at = datetime.utcnow()
    db.commit()
    return {"id": co.id, "status": co.status, "approved_at": co.approved_at.isoformat()}


@router.get("/summary")
def billing_summary(
    project_id: str = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    org_id = _get_user_org(current_user, db)
    q = db.query(Invoice).filter(Invoice.org_id == org_id)
    if project_id:
        q = q.filter(Invoice.project_id == project_id)

    invoices = q.all()

    total_invoiced = sum(inv.total_amount or 0 for inv in invoices)
    total_paid = sum(inv.amount_paid or 0 for inv in invoices)
    total_outstanding = sum(inv.balance_due or 0 for inv in invoices)
    invoice_count = len(invoices)
    avg_invoice = total_invoiced / invoice_count if invoice_count > 0 else 0

    by_status = {}
    for inv in invoices:
        status_val = inv.status.value if inv.status else "unknown"
        if status_val not in by_status:
            by_status[status_val] = {"count": 0, "total": 0}
        by_status[status_val]["count"] += 1
        by_status[status_val]["total"] += inv.total_amount or 0

    from dateutil.relativedelta import relativedelta
    now = datetime.utcnow()
    monthly_trend = []
    for i in range(5, -1, -1):
        month_start = (now - relativedelta(months=i)).replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        if i > 0:
            month_end = (now - relativedelta(months=i-1)).replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        else:
            month_end = now

        month_total = sum(
            inv.total_amount or 0 for inv in invoices
            if inv.created_at and month_start <= inv.created_at < month_end
        )
        monthly_trend.append({
            "month": month_start.strftime("%Y-%m"),
            "total": month_total
        })

    return {
        "total_invoiced": total_invoiced,
        "total_paid": total_paid,
        "total_outstanding": total_outstanding,
        "invoice_count": invoice_count,
        "avg_invoice": avg_invoice,
        "by_status": by_status,
        "monthly_trend": monthly_trend
    }
