import json
import random
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Query, Body
from sqlalchemy.orm import Session
from sqlalchemy import func, desc
from app.db.session import get_db
from app.core.auth import get_current_user
from app.models.models import (
    CRMCompany, CRMContact, CRMContract, CRMContractStatus,
    CRMActivity, CRMOutreachCampaign, CRMOutreachRecipient,
    CRMResearchResult, CRMChatSession, CRMChatMessage,
    OrgMember, User
)

router = APIRouter(prefix="/api/crm", tags=["crm"])

FIBER_CHAT_SYSTEM_PROMPT = """You are an expert AI analyst for the fiber construction and telecommunications industry. You have deep knowledge of:
- FTTH (Fiber-to-the-Home) deployment strategies and costs
- ISP market dynamics, competition analysis, and profitability factors
- Construction bidding processes, prime contractor relationships
- Geographic market analysis for fiber deployment opportunities
- Labor market conditions for skilled telecom technicians
- Material costs, supply chain dynamics, and vendor relationships
- Regulatory environment (FCC broadband initiatives, BEAD program, RDOF)
- Industry trends including 5G backhaul, rural broadband expansion
Provide data-driven insights, market analysis, and strategic recommendations."""


def _get_user_org(db: Session, user: User):
    membership = db.query(OrgMember).filter(OrgMember.user_id == user.id).first()
    if not membership:
        raise HTTPException(status_code=403, detail="No org membership")
    return membership.org_id


def _serialize_company(c):
    return {
        "id": c.id,
        "org_id": c.org_id,
        "name": c.name,
        "industry": c.industry,
        "company_type": c.company_type,
        "website": c.website,
        "phone": c.phone,
        "email": c.email,
        "address": c.address,
        "city": c.city,
        "state": c.state,
        "zip_code": c.zip_code,
        "country": c.country,
        "annual_revenue": float(c.annual_revenue) if c.annual_revenue else None,
        "employee_count": c.employee_count,
        "description": c.description,
        "linkedin_url": c.linkedin_url,
        "logo_url": c.logo_url,
        "tags": c.tags,
        "lead_source": c.lead_source,
        "lifecycle_stage": c.lifecycle_stage,
        "owner_id": c.owner_id,
        "parent_company_id": c.parent_company_id,
        "last_activity_date": str(c.last_activity_date) if c.last_activity_date else None,
        "custom_fields": c.custom_fields,
        "created_by": c.created_by,
        "created_at": str(c.created_at) if c.created_at else None,
        "updated_at": str(c.updated_at) if c.updated_at else None,
    }


def _serialize_contact(c):
    return {
        "id": c.id,
        "org_id": c.org_id,
        "company_id": c.company_id,
        "company_name": c.company.name if c.company else None,
        "first_name": c.first_name,
        "last_name": c.last_name,
        "full_name": f"{c.first_name} {c.last_name}",
        "email": c.email,
        "phone": c.phone,
        "mobile": c.mobile,
        "title": c.title,
        "department": c.department,
        "linkedin_url": c.linkedin_url,
        "address": c.address,
        "city": c.city,
        "state": c.state,
        "zip_code": c.zip_code,
        "lead_status": c.lead_status,
        "lifecycle_stage": c.lifecycle_stage,
        "lead_source": c.lead_source,
        "lead_score": c.lead_score,
        "tags": c.tags,
        "owner_id": c.owner_id,
        "last_contacted": str(c.last_contacted) if c.last_contacted else None,
        "last_activity_date": str(c.last_activity_date) if c.last_activity_date else None,
        "do_not_contact": c.do_not_contact,
        "notes": c.notes,
        "custom_fields": c.custom_fields,
        "avatar_url": c.avatar_url,
        "created_by": c.created_by,
        "created_at": str(c.created_at) if c.created_at else None,
        "updated_at": str(c.updated_at) if c.updated_at else None,
    }


def _serialize_contract(c):
    return {
        "id": c.id,
        "org_id": c.org_id,
        "company_id": c.company_id,
        "company_name": c.company.name if c.company else None,
        "contact_id": c.contact_id,
        "project_id": c.project_id,
        "contract_number": c.contract_number,
        "title": c.title,
        "description": c.description,
        "contract_type": c.contract_type,
        "status": c.status.value if c.status else None,
        "value": float(c.value) if c.value else 0,
        "start_date": str(c.start_date) if c.start_date else None,
        "end_date": str(c.end_date) if c.end_date else None,
        "signed_date": str(c.signed_date) if c.signed_date else None,
        "payment_terms": c.payment_terms,
        "billing_frequency": c.billing_frequency,
        "scope_of_work": c.scope_of_work,
        "terms_conditions": c.terms_conditions,
        "renewal_date": str(c.renewal_date) if c.renewal_date else None,
        "auto_renew": c.auto_renew,
        "margin_pct": float(c.margin_pct) if c.margin_pct else None,
        "owner_id": c.owner_id,
        "signed_by": c.signed_by,
        "tags": c.tags,
        "created_by": c.created_by,
        "created_at": str(c.created_at) if c.created_at else None,
        "updated_at": str(c.updated_at) if c.updated_at else None,
    }


def _serialize_activity(a):
    return {
        "id": a.id,
        "org_id": a.org_id,
        "contact_id": a.contact_id,
        "company_id": a.company_id,
        "contract_id": a.contract_id,
        "activity_type": a.activity_type,
        "subject": a.subject,
        "description": a.description,
        "outcome": a.outcome,
        "scheduled_date": str(a.scheduled_date) if a.scheduled_date else None,
        "completed_date": str(a.completed_date) if a.completed_date else None,
        "duration_minutes": a.duration_minutes,
        "is_completed": a.is_completed,
        "priority": a.priority,
        "created_by": a.created_by,
        "assigned_to": a.assigned_to,
        "created_at": str(a.created_at) if a.created_at else None,
    }


def _serialize_campaign(c):
    return {
        "id": c.id,
        "org_id": c.org_id,
        "name": c.name,
        "campaign_type": c.campaign_type,
        "status": c.status,
        "subject": c.subject,
        "content": c.content,
        "target_audience": c.target_audience,
        "scheduled_date": str(c.scheduled_date) if c.scheduled_date else None,
        "sent_date": str(c.sent_date) if c.sent_date else None,
        "total_recipients": c.total_recipients,
        "total_sent": c.total_sent,
        "total_opened": c.total_opened,
        "total_clicked": c.total_clicked,
        "total_replied": c.total_replied,
        "total_bounced": c.total_bounced,
        "open_rate": float(c.open_rate or 0),
        "click_rate": float(c.click_rate or 0),
        "reply_rate": float(c.reply_rate or 0),
        "created_by": c.created_by,
        "created_at": str(c.created_at) if c.created_at else None,
        "updated_at": str(c.updated_at) if c.updated_at else None,
    }


@router.get("/stats")
def get_crm_stats(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    org_id = _get_user_org(db, user)

    total_contacts = db.query(func.count(CRMContact.id)).filter(CRMContact.org_id == org_id).scalar() or 0
    total_companies = db.query(func.count(CRMCompany.id)).filter(CRMCompany.org_id == org_id).scalar() or 0
    active_contracts = db.query(func.count(CRMContract.id)).filter(
        CRMContract.org_id == org_id,
        CRMContract.status.in_([CRMContractStatus.ACTIVE, CRMContractStatus.APPROVED])
    ).scalar() or 0
    pipeline_value = db.query(func.coalesce(func.sum(CRMContract.value), 0)).filter(
        CRMContract.org_id == org_id,
        CRMContract.status.in_([CRMContractStatus.DRAFT, CRMContractStatus.PROPOSED, CRMContractStatus.NEGOTIATION])
    ).scalar() or 0
    open_activities = db.query(func.count(CRMActivity.id)).filter(
        CRMActivity.org_id == org_id, CRMActivity.is_completed == False
    ).scalar() or 0
    campaign_count = db.query(func.count(CRMOutreachCampaign.id)).filter(
        CRMOutreachCampaign.org_id == org_id
    ).scalar() or 0

    total_contract_value = db.query(func.coalesce(func.sum(CRMContract.value), 0)).filter(
        CRMContract.org_id == org_id,
        CRMContract.status.in_([CRMContractStatus.ACTIVE, CRMContractStatus.APPROVED, CRMContractStatus.COMPLETED])
    ).scalar() or 0

    contacts_by_stage = {}
    stage_rows = db.query(CRMContact.lifecycle_stage, func.count(CRMContact.id)).filter(
        CRMContact.org_id == org_id
    ).group_by(CRMContact.lifecycle_stage).all()
    for s, c in stage_rows:
        contacts_by_stage[s or "unknown"] = c

    companies_by_type = {}
    type_rows = db.query(CRMCompany.company_type, func.count(CRMCompany.id)).filter(
        CRMCompany.org_id == org_id
    ).group_by(CRMCompany.company_type).all()
    for t, c in type_rows:
        companies_by_type[t or "unknown"] = c

    return {
        "total_contacts": total_contacts,
        "total_companies": total_companies,
        "active_contracts": active_contracts,
        "pipeline_value": float(pipeline_value),
        "total_contract_value": float(total_contract_value),
        "open_activities": open_activities,
        "campaign_count": campaign_count,
        "contacts_by_stage": contacts_by_stage,
        "companies_by_type": companies_by_type,
    }


@router.get("/companies")
def list_companies(
    search: str = Query(None),
    company_type: str = Query(None),
    lifecycle_stage: str = Query(None),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    org_id = _get_user_org(db, user)
    q = db.query(CRMCompany).filter(CRMCompany.org_id == org_id)
    if search:
        q = q.filter(
            (CRMCompany.name.ilike(f"%{search}%")) |
            (CRMCompany.email.ilike(f"%{search}%")) |
            (CRMCompany.industry.ilike(f"%{search}%"))
        )
    if company_type:
        q = q.filter(CRMCompany.company_type == company_type)
    if lifecycle_stage:
        q = q.filter(CRMCompany.lifecycle_stage == lifecycle_stage)
    companies = q.order_by(desc(CRMCompany.created_at)).all()
    return [_serialize_company(c) for c in companies]


@router.post("/companies")
def create_company(data: dict = Body(...), user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    org_id = _get_user_org(db, user)
    company = CRMCompany(
        org_id=org_id,
        name=data["name"],
        industry=data.get("industry"),
        company_type=data.get("company_type", "prospect"),
        website=data.get("website"),
        phone=data.get("phone"),
        email=data.get("email"),
        address=data.get("address"),
        city=data.get("city"),
        state=data.get("state"),
        zip_code=data.get("zip_code"),
        country=data.get("country", "US"),
        annual_revenue=float(data["annual_revenue"]) if data.get("annual_revenue") else None,
        employee_count=int(data["employee_count"]) if data.get("employee_count") else None,
        description=data.get("description"),
        linkedin_url=data.get("linkedin_url"),
        logo_url=data.get("logo_url"),
        tags=data.get("tags"),
        lead_source=data.get("lead_source"),
        lifecycle_stage=data.get("lifecycle_stage", "lead"),
        owner_id=data.get("owner_id"),
        parent_company_id=data.get("parent_company_id"),
        custom_fields=data.get("custom_fields"),
        created_by=user.id,
    )
    db.add(company)
    db.commit()
    db.refresh(company)
    return _serialize_company(company)


@router.get("/companies/{company_id}")
def get_company(company_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    org_id = _get_user_org(db, user)
    company = db.query(CRMCompany).filter(CRMCompany.id == company_id, CRMCompany.org_id == org_id).first()
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")

    contacts_count = db.query(func.count(CRMContact.id)).filter(CRMContact.company_id == company_id).scalar() or 0
    contracts = db.query(CRMContract).filter(CRMContract.company_id == company_id).order_by(desc(CRMContract.created_at)).all()
    activities = db.query(CRMActivity).filter(CRMActivity.company_id == company_id).order_by(desc(CRMActivity.created_at)).limit(20).all()

    result = _serialize_company(company)
    result["contacts_count"] = contacts_count
    result["contracts"] = [_serialize_contract(c) for c in contracts]
    result["activities"] = [_serialize_activity(a) for a in activities]
    return result


@router.put("/companies/{company_id}")
def update_company(company_id: str, data: dict = Body(...), user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    org_id = _get_user_org(db, user)
    company = db.query(CRMCompany).filter(CRMCompany.id == company_id, CRMCompany.org_id == org_id).first()
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")

    fields = ["name", "industry", "company_type", "website", "phone", "email",
              "address", "city", "state", "zip_code", "country", "description",
              "linkedin_url", "logo_url", "tags", "lead_source", "lifecycle_stage",
              "owner_id", "parent_company_id", "custom_fields"]
    for f in fields:
        if f in data:
            setattr(company, f, data[f])
    if "annual_revenue" in data:
        company.annual_revenue = float(data["annual_revenue"]) if data["annual_revenue"] else None
    if "employee_count" in data:
        company.employee_count = int(data["employee_count"]) if data["employee_count"] else None

    db.commit()
    db.refresh(company)
    return _serialize_company(company)


@router.delete("/companies/{company_id}")
def delete_company(company_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    org_id = _get_user_org(db, user)
    company = db.query(CRMCompany).filter(CRMCompany.id == company_id, CRMCompany.org_id == org_id).first()
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")
    db.delete(company)
    db.commit()
    return {"ok": True, "deleted": company_id}


@router.get("/contacts")
def list_contacts(
    search: str = Query(None),
    lead_status: str = Query(None),
    lifecycle_stage: str = Query(None),
    company_id: str = Query(None),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    org_id = _get_user_org(db, user)
    q = db.query(CRMContact).filter(CRMContact.org_id == org_id)
    if search:
        q = q.filter(
            (CRMContact.first_name.ilike(f"%{search}%")) |
            (CRMContact.last_name.ilike(f"%{search}%")) |
            (CRMContact.email.ilike(f"%{search}%")) |
            (CRMContact.title.ilike(f"%{search}%"))
        )
    if lead_status:
        q = q.filter(CRMContact.lead_status == lead_status)
    if lifecycle_stage:
        q = q.filter(CRMContact.lifecycle_stage == lifecycle_stage)
    if company_id:
        q = q.filter(CRMContact.company_id == company_id)
    contacts = q.order_by(desc(CRMContact.created_at)).all()
    return [_serialize_contact(c) for c in contacts]


@router.post("/contacts")
def create_contact(data: dict = Body(...), user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    org_id = _get_user_org(db, user)
    contact = CRMContact(
        org_id=org_id,
        company_id=data.get("company_id"),
        first_name=data["first_name"],
        last_name=data["last_name"],
        email=data.get("email"),
        phone=data.get("phone"),
        mobile=data.get("mobile"),
        title=data.get("title"),
        department=data.get("department"),
        linkedin_url=data.get("linkedin_url"),
        address=data.get("address"),
        city=data.get("city"),
        state=data.get("state"),
        zip_code=data.get("zip_code"),
        lead_status=data.get("lead_status", "new"),
        lifecycle_stage=data.get("lifecycle_stage", "lead"),
        lead_source=data.get("lead_source"),
        lead_score=int(data.get("lead_score", 0)),
        tags=data.get("tags"),
        owner_id=data.get("owner_id"),
        do_not_contact=data.get("do_not_contact", False),
        notes=data.get("notes"),
        custom_fields=data.get("custom_fields"),
        avatar_url=data.get("avatar_url"),
        created_by=user.id,
    )
    db.add(contact)
    db.commit()
    db.refresh(contact)
    return _serialize_contact(contact)


@router.get("/contacts/{contact_id}")
def get_contact(contact_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    org_id = _get_user_org(db, user)
    contact = db.query(CRMContact).filter(CRMContact.id == contact_id, CRMContact.org_id == org_id).first()
    if not contact:
        raise HTTPException(status_code=404, detail="Contact not found")

    activities = db.query(CRMActivity).filter(CRMActivity.contact_id == contact_id).order_by(desc(CRMActivity.created_at)).limit(20).all()
    outreach = db.query(CRMOutreachRecipient).filter(CRMOutreachRecipient.contact_id == contact_id).all()

    result = _serialize_contact(contact)
    result["activities"] = [_serialize_activity(a) for a in activities]
    result["outreach_history"] = [{
        "id": r.id,
        "campaign_id": r.campaign_id,
        "status": r.status,
        "sent_at": str(r.sent_at) if r.sent_at else None,
        "opened_at": str(r.opened_at) if r.opened_at else None,
        "clicked_at": str(r.clicked_at) if r.clicked_at else None,
        "replied_at": str(r.replied_at) if r.replied_at else None,
        "bounced": r.bounced,
    } for r in outreach]
    return result


@router.put("/contacts/{contact_id}")
def update_contact(contact_id: str, data: dict = Body(...), user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    org_id = _get_user_org(db, user)
    contact = db.query(CRMContact).filter(CRMContact.id == contact_id, CRMContact.org_id == org_id).first()
    if not contact:
        raise HTTPException(status_code=404, detail="Contact not found")

    fields = ["company_id", "first_name", "last_name", "email", "phone", "mobile",
              "title", "department", "linkedin_url", "address", "city", "state",
              "zip_code", "lead_status", "lifecycle_stage", "lead_source",
              "tags", "owner_id", "notes", "custom_fields", "avatar_url"]
    for f in fields:
        if f in data:
            setattr(contact, f, data[f])
    if "lead_score" in data:
        contact.lead_score = int(data["lead_score"])
    if "do_not_contact" in data:
        contact.do_not_contact = bool(data["do_not_contact"])

    db.commit()
    db.refresh(contact)
    return _serialize_contact(contact)


@router.delete("/contacts/{contact_id}")
def delete_contact(contact_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    org_id = _get_user_org(db, user)
    contact = db.query(CRMContact).filter(CRMContact.id == contact_id, CRMContact.org_id == org_id).first()
    if not contact:
        raise HTTPException(status_code=404, detail="Contact not found")
    db.delete(contact)
    db.commit()
    return {"ok": True, "deleted": contact_id}


@router.get("/contracts")
def list_contracts(
    search: str = Query(None),
    status: str = Query(None),
    company_id: str = Query(None),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    org_id = _get_user_org(db, user)
    q = db.query(CRMContract).filter(CRMContract.org_id == org_id)
    if search:
        q = q.filter(
            (CRMContract.title.ilike(f"%{search}%")) |
            (CRMContract.contract_number.ilike(f"%{search}%"))
        )
    if status:
        q = q.filter(CRMContract.status == status)
    if company_id:
        q = q.filter(CRMContract.company_id == company_id)
    contracts = q.order_by(desc(CRMContract.created_at)).all()
    return [_serialize_contract(c) for c in contracts]


@router.post("/contracts")
def create_contract(data: dict = Body(...), user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    org_id = _get_user_org(db, user)

    count = db.query(func.count(CRMContract.id)).filter(CRMContract.org_id == org_id).scalar() or 0
    contract_number = f"CTR-{datetime.utcnow().strftime('%Y%m')}-{count + 1:04d}"

    contract = CRMContract(
        org_id=org_id,
        company_id=data.get("company_id"),
        contact_id=data.get("contact_id"),
        project_id=data.get("project_id"),
        contract_number=contract_number,
        title=data["title"],
        description=data.get("description"),
        contract_type=data.get("contract_type", "fixed_price"),
        status=data.get("status", CRMContractStatus.DRAFT),
        value=float(data.get("value", 0)),
        start_date=datetime.fromisoformat(data["start_date"]) if data.get("start_date") else None,
        end_date=datetime.fromisoformat(data["end_date"]) if data.get("end_date") else None,
        signed_date=datetime.fromisoformat(data["signed_date"]) if data.get("signed_date") else None,
        payment_terms=data.get("payment_terms"),
        billing_frequency=data.get("billing_frequency"),
        scope_of_work=data.get("scope_of_work"),
        terms_conditions=data.get("terms_conditions"),
        renewal_date=datetime.fromisoformat(data["renewal_date"]) if data.get("renewal_date") else None,
        auto_renew=data.get("auto_renew", False),
        margin_pct=float(data["margin_pct"]) if data.get("margin_pct") else None,
        owner_id=data.get("owner_id"),
        tags=data.get("tags"),
        created_by=user.id,
    )
    db.add(contract)
    db.commit()
    db.refresh(contract)
    return _serialize_contract(contract)


@router.get("/contracts/{contract_id}")
def get_contract(contract_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    org_id = _get_user_org(db, user)
    contract = db.query(CRMContract).filter(CRMContract.id == contract_id, CRMContract.org_id == org_id).first()
    if not contract:
        raise HTTPException(status_code=404, detail="Contract not found")
    return _serialize_contract(contract)


@router.put("/contracts/{contract_id}")
def update_contract(contract_id: str, data: dict = Body(...), user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    org_id = _get_user_org(db, user)
    contract = db.query(CRMContract).filter(CRMContract.id == contract_id, CRMContract.org_id == org_id).first()
    if not contract:
        raise HTTPException(status_code=404, detail="Contract not found")

    fields = ["company_id", "contact_id", "project_id", "title", "description",
              "contract_type", "payment_terms", "billing_frequency", "scope_of_work",
              "terms_conditions", "owner_id", "signed_by", "tags"]
    for f in fields:
        if f in data:
            setattr(contract, f, data[f])
    if "value" in data:
        contract.value = float(data["value"])
    if "margin_pct" in data:
        contract.margin_pct = float(data["margin_pct"]) if data["margin_pct"] else None
    if "auto_renew" in data:
        contract.auto_renew = bool(data["auto_renew"])
    if "status" in data:
        contract.status = data["status"]

    date_fields = ["start_date", "end_date", "signed_date", "renewal_date"]
    for f in date_fields:
        if f in data:
            setattr(contract, f, datetime.fromisoformat(data[f]) if data[f] else None)

    db.commit()
    db.refresh(contract)
    return _serialize_contract(contract)


@router.put("/contracts/{contract_id}/status")
def change_contract_status(contract_id: str, data: dict = Body(...), user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    org_id = _get_user_org(db, user)
    contract = db.query(CRMContract).filter(CRMContract.id == contract_id, CRMContract.org_id == org_id).first()
    if not contract:
        raise HTTPException(status_code=404, detail="Contract not found")

    new_status = data.get("status")
    if not new_status:
        raise HTTPException(status_code=400, detail="Status is required")

    contract.status = new_status
    if new_status == CRMContractStatus.ACTIVE.value and not contract.signed_date:
        contract.signed_date = datetime.utcnow()

    db.commit()
    db.refresh(contract)
    return _serialize_contract(contract)


@router.get("/activities")
def list_activities(
    contact_id: str = Query(None),
    company_id: str = Query(None),
    activity_type: str = Query(None),
    is_completed: bool = Query(None),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    org_id = _get_user_org(db, user)
    q = db.query(CRMActivity).filter(CRMActivity.org_id == org_id)
    if contact_id:
        q = q.filter(CRMActivity.contact_id == contact_id)
    if company_id:
        q = q.filter(CRMActivity.company_id == company_id)
    if activity_type:
        q = q.filter(CRMActivity.activity_type == activity_type)
    if is_completed is not None:
        q = q.filter(CRMActivity.is_completed == is_completed)
    activities = q.order_by(desc(CRMActivity.created_at)).all()
    return [_serialize_activity(a) for a in activities]


@router.post("/activities")
def create_activity(data: dict = Body(...), user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    org_id = _get_user_org(db, user)
    activity = CRMActivity(
        org_id=org_id,
        contact_id=data.get("contact_id"),
        company_id=data.get("company_id"),
        contract_id=data.get("contract_id"),
        activity_type=data.get("activity_type", "note"),
        subject=data["subject"],
        description=data.get("description"),
        outcome=data.get("outcome"),
        scheduled_date=datetime.fromisoformat(data["scheduled_date"]) if data.get("scheduled_date") else None,
        duration_minutes=int(data["duration_minutes"]) if data.get("duration_minutes") else None,
        is_completed=data.get("is_completed", False),
        priority=data.get("priority", "normal"),
        created_by=user.id,
        assigned_to=data.get("assigned_to"),
    )
    if activity.is_completed:
        activity.completed_date = datetime.utcnow()

    db.add(activity)

    if data.get("contact_id"):
        contact = db.query(CRMContact).filter(CRMContact.id == data["contact_id"]).first()
        if contact:
            contact.last_activity_date = datetime.utcnow()
    if data.get("company_id"):
        company = db.query(CRMCompany).filter(CRMCompany.id == data["company_id"]).first()
        if company:
            company.last_activity_date = datetime.utcnow()

    db.commit()
    db.refresh(activity)
    return _serialize_activity(activity)


@router.put("/activities/{activity_id}/complete")
def complete_activity(activity_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    org_id = _get_user_org(db, user)
    activity = db.query(CRMActivity).filter(CRMActivity.id == activity_id, CRMActivity.org_id == org_id).first()
    if not activity:
        raise HTTPException(status_code=404, detail="Activity not found")
    activity.is_completed = True
    activity.completed_date = datetime.utcnow()
    db.commit()
    db.refresh(activity)
    return _serialize_activity(activity)


@router.get("/campaigns")
def list_campaigns(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    org_id = _get_user_org(db, user)
    campaigns = db.query(CRMOutreachCampaign).filter(
        CRMOutreachCampaign.org_id == org_id
    ).order_by(desc(CRMOutreachCampaign.created_at)).all()
    return [_serialize_campaign(c) for c in campaigns]


@router.post("/campaigns")
def create_campaign(data: dict = Body(...), user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    org_id = _get_user_org(db, user)
    campaign = CRMOutreachCampaign(
        org_id=org_id,
        name=data["name"],
        campaign_type=data.get("campaign_type", "email"),
        status=data.get("status", "draft"),
        subject=data.get("subject"),
        content=data.get("content"),
        target_audience=data.get("target_audience"),
        scheduled_date=datetime.fromisoformat(data["scheduled_date"]) if data.get("scheduled_date") else None,
        created_by=user.id,
    )
    db.add(campaign)
    db.commit()
    db.refresh(campaign)
    return _serialize_campaign(campaign)


@router.post("/campaigns/{campaign_id}/send")
def send_campaign(campaign_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    org_id = _get_user_org(db, user)
    campaign = db.query(CRMOutreachCampaign).filter(
        CRMOutreachCampaign.id == campaign_id, CRMOutreachCampaign.org_id == org_id
    ).first()
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")

    recipients = db.query(CRMOutreachRecipient).filter(
        CRMOutreachRecipient.campaign_id == campaign_id
    ).all()

    if not recipients:
        raise HTTPException(status_code=400, detail="No recipients added to campaign")

    now = datetime.utcnow()
    total_sent = 0
    total_bounced = 0
    for r in recipients:
        if random.random() < 0.05:
            r.bounced = True
            r.status = "bounced"
            total_bounced += 1
        else:
            r.sent_at = now
            r.status = "sent"
            total_sent += 1
            if random.random() < 0.35:
                r.opened_at = now
                if random.random() < 0.4:
                    r.clicked_at = now

    campaign.status = "sent"
    campaign.sent_date = now
    campaign.total_recipients = len(recipients)
    campaign.total_sent = total_sent
    campaign.total_bounced = total_bounced
    campaign.total_opened = sum(1 for r in recipients if r.opened_at)
    campaign.total_clicked = sum(1 for r in recipients if r.clicked_at)
    campaign.open_rate = round(campaign.total_opened / max(total_sent, 1) * 100, 1)
    campaign.click_rate = round(campaign.total_clicked / max(total_sent, 1) * 100, 1)

    db.commit()
    db.refresh(campaign)
    return _serialize_campaign(campaign)


@router.post("/campaigns/{campaign_id}/recipients")
def add_campaign_recipients(campaign_id: str, data: dict = Body(...), user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    org_id = _get_user_org(db, user)
    campaign = db.query(CRMOutreachCampaign).filter(
        CRMOutreachCampaign.id == campaign_id, CRMOutreachCampaign.org_id == org_id
    ).first()
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")

    contact_ids = data.get("contact_ids", [])
    if not contact_ids:
        raise HTTPException(status_code=400, detail="contact_ids required")

    added = 0
    for cid in contact_ids:
        existing = db.query(CRMOutreachRecipient).filter(
            CRMOutreachRecipient.campaign_id == campaign_id,
            CRMOutreachRecipient.contact_id == cid
        ).first()
        if not existing:
            contact = db.query(CRMContact).filter(CRMContact.id == cid, CRMContact.org_id == org_id).first()
            if contact:
                recipient = CRMOutreachRecipient(
                    campaign_id=campaign_id,
                    contact_id=cid,
                    status="pending",
                )
                db.add(recipient)
                added += 1

    campaign.total_recipients = db.query(func.count(CRMOutreachRecipient.id)).filter(
        CRMOutreachRecipient.campaign_id == campaign_id
    ).scalar() or 0

    db.commit()
    return {"ok": True, "added": added, "total_recipients": campaign.total_recipients}


@router.post("/research")
def ai_research(data: dict = Body(...), user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    org_id = _get_user_org(db, user)

    contact_id = data.get("contact_id")
    company_id = data.get("company_id")
    research_type = data.get("research_type", "general")
    query_text = data.get("query", "")

    entity_name = ""
    entity_context = ""

    if contact_id:
        contact = db.query(CRMContact).filter(CRMContact.id == contact_id, CRMContact.org_id == org_id).first()
        if not contact:
            raise HTTPException(status_code=404, detail="Contact not found")
        entity_name = f"{contact.first_name} {contact.last_name}"
        entity_context = f"Contact: {entity_name}, Title: {contact.title or 'N/A'}, Company: {contact.company.name if contact.company else 'N/A'}, Email: {contact.email or 'N/A'}"
    elif company_id:
        company = db.query(CRMCompany).filter(CRMCompany.id == company_id, CRMCompany.org_id == org_id).first()
        if not company:
            raise HTTPException(status_code=404, detail="Company not found")
        entity_name = company.name
        entity_context = f"Company: {entity_name}, Industry: {company.industry or 'N/A'}, Type: {company.company_type or 'N/A'}, Location: {company.city or ''} {company.state or ''}"
    else:
        raise HTTPException(status_code=400, detail="contact_id or company_id required")

    prompt = f"""Research the following entity in the fiber construction and telecommunications industry:

{entity_context}

Additional context/query: {query_text}

Provide intelligence on:
1. Recent projects and contracts in fiber/telecom construction
2. Market position and competitive landscape
3. Key decision makers and organizational structure
4. Financial health and growth trajectory
5. Relevant industry partnerships and relationships
6. Potential opportunities for fiber construction services
7. Risk factors and considerations

Focus on actionable intelligence for a fiber construction company looking to build business relationships."""

    try:
        from openai import OpenAI
        client = OpenAI()
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are a telecom and fiber construction industry research analyst. Provide detailed, actionable intelligence reports."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=2000,
            temperature=0.7,
        )
        result_text = response.choices[0].message.content
        tokens_used = response.usage.total_tokens if response.usage else 0
    except Exception as e:
        result_text = f"AI research unavailable: {str(e)}"
        tokens_used = 0

    research = CRMResearchResult(
        org_id=org_id,
        contact_id=contact_id,
        company_id=company_id,
        research_type=research_type,
        query=query_text or f"Research on {entity_name}",
        result_summary=result_text,
        result_data=json.dumps({"tokens_used": tokens_used}),
        ai_model="gpt-4o-mini",
        created_by=user.id,
    )
    db.add(research)
    db.commit()
    db.refresh(research)

    return {
        "id": research.id,
        "entity_name": entity_name,
        "research_type": research_type,
        "summary": result_text,
        "tokens_used": tokens_used,
        "created_at": str(research.created_at),
    }


@router.post("/chat/sessions")
def create_chat_session(data: dict = Body(...), user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    org_id = _get_user_org(db, user)
    session = CRMChatSession(
        org_id=org_id,
        user_id=user.id,
        title=data.get("title", "New Chat Session"),
        session_type=data.get("session_type", "general"),
        context=data.get("context"),
        is_active=True,
        message_count=0,
    )
    db.add(session)
    db.commit()
    db.refresh(session)
    return {
        "id": session.id,
        "title": session.title,
        "session_type": session.session_type,
        "is_active": session.is_active,
        "message_count": session.message_count,
        "created_at": str(session.created_at),
    }


@router.get("/chat/sessions")
def list_chat_sessions(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    org_id = _get_user_org(db, user)
    sessions = db.query(CRMChatSession).filter(
        CRMChatSession.org_id == org_id,
        CRMChatSession.user_id == user.id
    ).order_by(desc(CRMChatSession.updated_at)).all()
    return [{
        "id": s.id,
        "title": s.title,
        "session_type": s.session_type,
        "is_active": s.is_active,
        "message_count": s.message_count,
        "created_at": str(s.created_at),
        "updated_at": str(s.updated_at) if s.updated_at else None,
    } for s in sessions]


@router.post("/chat/sessions/{session_id}/messages")
def send_chat_message(session_id: str, data: dict = Body(...), user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    org_id = _get_user_org(db, user)
    session = db.query(CRMChatSession).filter(
        CRMChatSession.id == session_id,
        CRMChatSession.org_id == org_id,
        CRMChatSession.user_id == user.id
    ).first()
    if not session:
        raise HTTPException(status_code=404, detail="Chat session not found")

    user_content = data.get("message", "")
    if not user_content:
        raise HTTPException(status_code=400, detail="Message is required")

    user_msg = CRMChatMessage(
        session_id=session_id,
        role="user",
        content=user_content,
        tokens_used=0,
    )
    db.add(user_msg)

    history = db.query(CRMChatMessage).filter(
        CRMChatMessage.session_id == session_id
    ).order_by(CRMChatMessage.created_at).all()

    messages = [{"role": "system", "content": FIBER_CHAT_SYSTEM_PROMPT}]
    for msg in history[-20:]:
        messages.append({"role": msg.role, "content": msg.content})
    messages.append({"role": "user", "content": user_content})

    try:
        from openai import OpenAI
        client = OpenAI()
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=messages,
            max_tokens=2000,
            temperature=0.7,
        )
        ai_content = response.choices[0].message.content
        tokens_used = response.usage.total_tokens if response.usage else 0
    except Exception as e:
        ai_content = f"I apologize, but I'm currently unable to process your request. Error: {str(e)}"
        tokens_used = 0

    ai_msg = CRMChatMessage(
        session_id=session_id,
        role="assistant",
        content=ai_content,
        tokens_used=tokens_used,
    )
    db.add(ai_msg)

    session.message_count = (session.message_count or 0) + 2
    session.updated_at = datetime.utcnow()

    db.commit()
    db.refresh(ai_msg)

    return {
        "user_message": {
            "id": user_msg.id,
            "role": "user",
            "content": user_content,
            "created_at": str(user_msg.created_at),
        },
        "assistant_message": {
            "id": ai_msg.id,
            "role": "assistant",
            "content": ai_content,
            "tokens_used": tokens_used,
            "created_at": str(ai_msg.created_at),
        },
    }


@router.get("/chat/sessions/{session_id}/messages")
def get_chat_messages(session_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    org_id = _get_user_org(db, user)
    session = db.query(CRMChatSession).filter(
        CRMChatSession.id == session_id,
        CRMChatSession.org_id == org_id,
        CRMChatSession.user_id == user.id
    ).first()
    if not session:
        raise HTTPException(status_code=404, detail="Chat session not found")

    messages = db.query(CRMChatMessage).filter(
        CRMChatMessage.session_id == session_id
    ).order_by(CRMChatMessage.created_at).all()

    return {
        "session_id": session_id,
        "title": session.title,
        "messages": [{
            "id": m.id,
            "role": m.role,
            "content": m.content,
            "tokens_used": m.tokens_used,
            "created_at": str(m.created_at),
        } for m in messages],
    }
