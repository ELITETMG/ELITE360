from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Query, Body
from sqlalchemy.orm import Session
from sqlalchemy import func, desc
from app.db.session import get_db
from app.core.auth import get_current_user
from app.models.models import (
    Account, AccountType, JournalEntry, JournalEntryLine,
    AccountsPayable, AccountsReceivable, APStatus, ARStatus,
    OrgMember, User
)

router = APIRouter(prefix="/api/accounting", tags=["accounting"])


def _get_user_org(db: Session, user: User):
    membership = db.query(OrgMember).filter(OrgMember.user_id == user.id).first()
    if not membership:
        raise HTTPException(status_code=403, detail="No org membership")
    return membership.org_id


def _serialize_account(a):
    return {
        "id": str(a.id),
        "org_id": str(a.org_id),
        "account_number": a.account_number,
        "name": a.name,
        "account_type": a.account_type.value if a.account_type else None,
        "parent_id": str(a.parent_id) if a.parent_id else None,
        "description": a.description,
        "is_active": a.is_active,
        "normal_balance": a.normal_balance,
        "balance": float(a.balance or 0),
        "created_at": a.created_at.isoformat() if a.created_at else None,
        "updated_at": a.updated_at.isoformat() if a.updated_at else None,
    }


def _serialize_journal_entry(je, lines=None):
    result = {
        "id": str(je.id),
        "org_id": str(je.org_id),
        "entry_number": je.entry_number,
        "entry_date": je.entry_date.isoformat() if je.entry_date else None,
        "description": je.description,
        "reference": je.reference,
        "source": je.source,
        "is_posted": je.is_posted,
        "is_reversing": je.is_reversing,
        "reversed_entry_id": str(je.reversed_entry_id) if je.reversed_entry_id else None,
        "total_debit": float(je.total_debit or 0),
        "total_credit": float(je.total_credit or 0),
        "created_by": str(je.created_by),
        "approved_by": str(je.approved_by) if je.approved_by else None,
        "posted_at": je.posted_at.isoformat() if je.posted_at else None,
        "created_at": je.created_at.isoformat() if je.created_at else None,
    }
    if lines is not None:
        result["lines"] = [_serialize_journal_line(l) for l in lines]
    return result


def _serialize_journal_line(l):
    return {
        "id": str(l.id),
        "entry_id": str(l.entry_id),
        "account_id": str(l.account_id),
        "account_name": l.account.name if l.account else None,
        "account_number": l.account.account_number if l.account else None,
        "description": l.description,
        "debit": float(l.debit or 0),
        "credit": float(l.credit or 0),
        "project_id": str(l.project_id) if l.project_id else None,
    }


def _serialize_ap(ap):
    return {
        "id": str(ap.id),
        "org_id": str(ap.org_id),
        "vendor_name": ap.vendor_name,
        "vendor_contact": ap.vendor_contact,
        "invoice_number": ap.invoice_number,
        "invoice_date": ap.invoice_date.isoformat() if ap.invoice_date else None,
        "due_date": ap.due_date.isoformat() if ap.due_date else None,
        "amount": float(ap.amount or 0),
        "amount_paid": float(ap.amount_paid or 0),
        "status": ap.status.value if ap.status else None,
        "account_id": str(ap.account_id) if ap.account_id else None,
        "project_id": str(ap.project_id) if ap.project_id else None,
        "description": ap.description,
        "payment_terms": ap.payment_terms,
        "payment_method": ap.payment_method,
        "paid_date": ap.paid_date.isoformat() if ap.paid_date else None,
        "created_by": str(ap.created_by),
        "created_at": ap.created_at.isoformat() if ap.created_at else None,
        "updated_at": ap.updated_at.isoformat() if ap.updated_at else None,
    }


def _serialize_ar(ar):
    return {
        "id": str(ar.id),
        "org_id": str(ar.org_id),
        "customer_name": ar.customer_name,
        "customer_contact": ar.customer_contact,
        "invoice_id": str(ar.invoice_id) if ar.invoice_id else None,
        "invoice_number": ar.invoice_number,
        "invoice_date": ar.invoice_date.isoformat() if ar.invoice_date else None,
        "due_date": ar.due_date.isoformat() if ar.due_date else None,
        "amount": float(ar.amount or 0),
        "amount_received": float(ar.amount_received or 0),
        "status": ar.status.value if ar.status else None,
        "account_id": str(ar.account_id) if ar.account_id else None,
        "project_id": str(ar.project_id) if ar.project_id else None,
        "description": ar.description,
        "payment_terms": ar.payment_terms,
        "last_payment_date": ar.last_payment_date.isoformat() if ar.last_payment_date else None,
        "created_by": str(ar.created_by),
        "created_at": ar.created_at.isoformat() if ar.created_at else None,
        "updated_at": ar.updated_at.isoformat() if ar.updated_at else None,
    }


@router.get("/stats")
def get_accounting_stats(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    org_id = _get_user_org(db, user)

    total_accounts = db.query(func.count(Account.id)).filter(Account.org_id == org_id).scalar() or 0
    active_accounts = db.query(func.count(Account.id)).filter(Account.org_id == org_id, Account.is_active == True).scalar() or 0

    ap_outstanding = db.query(func.coalesce(func.sum(AccountsPayable.amount - AccountsPayable.amount_paid), 0)).filter(
        AccountsPayable.org_id == org_id,
        AccountsPayable.status.in_([APStatus.PENDING, APStatus.APPROVED, APStatus.OVERDUE])
    ).scalar() or 0

    ar_outstanding = db.query(func.coalesce(func.sum(AccountsReceivable.amount - AccountsReceivable.amount_received), 0)).filter(
        AccountsReceivable.org_id == org_id,
        AccountsReceivable.status.in_([ARStatus.OUTSTANDING, ARStatus.PARTIAL, ARStatus.OVERDUE])
    ).scalar() or 0

    total_revenue = db.query(func.coalesce(func.sum(Account.balance), 0)).filter(
        Account.org_id == org_id, Account.account_type == AccountType.REVENUE
    ).scalar() or 0

    total_expenses = db.query(func.coalesce(func.sum(Account.balance), 0)).filter(
        Account.org_id == org_id, Account.account_type == AccountType.EXPENSE
    ).scalar() or 0

    net_income = float(total_revenue) - float(total_expenses)

    total_assets = db.query(func.coalesce(func.sum(Account.balance), 0)).filter(
        Account.org_id == org_id, Account.account_type == AccountType.ASSET
    ).scalar() or 0

    total_liabilities = db.query(func.coalesce(func.sum(Account.balance), 0)).filter(
        Account.org_id == org_id, Account.account_type == AccountType.LIABILITY
    ).scalar() or 0

    total_equity = db.query(func.coalesce(func.sum(Account.balance), 0)).filter(
        Account.org_id == org_id, Account.account_type == AccountType.EQUITY
    ).scalar() or 0

    journal_count = db.query(func.count(JournalEntry.id)).filter(JournalEntry.org_id == org_id).scalar() or 0
    posted_count = db.query(func.count(JournalEntry.id)).filter(
        JournalEntry.org_id == org_id, JournalEntry.is_posted == True
    ).scalar() or 0
    unposted_count = journal_count - posted_count

    ap_overdue = db.query(func.count(AccountsPayable.id)).filter(
        AccountsPayable.org_id == org_id, AccountsPayable.status == APStatus.OVERDUE
    ).scalar() or 0

    ar_overdue = db.query(func.count(AccountsReceivable.id)).filter(
        AccountsReceivable.org_id == org_id, AccountsReceivable.status == ARStatus.OVERDUE
    ).scalar() or 0

    return {
        "total_accounts": total_accounts,
        "active_accounts": active_accounts,
        "ap_outstanding": float(ap_outstanding),
        "ar_outstanding": float(ar_outstanding),
        "net_income": net_income,
        "total_revenue": float(total_revenue),
        "total_expenses": float(total_expenses),
        "total_assets": float(total_assets),
        "total_liabilities": float(total_liabilities),
        "total_equity": float(total_equity),
        "journal_entries": journal_count,
        "posted_entries": posted_count,
        "unposted_entries": unposted_count,
        "ap_overdue_count": ap_overdue,
        "ar_overdue_count": ar_overdue,
    }


@router.get("/accounts")
def list_accounts(
    account_type: str = Query(None),
    is_active: bool = Query(None),
    search: str = Query(None),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    org_id = _get_user_org(db, user)
    q = db.query(Account).filter(Account.org_id == org_id)
    if account_type:
        q = q.filter(Account.account_type == account_type)
    if is_active is not None:
        q = q.filter(Account.is_active == is_active)
    if search:
        q = q.filter(
            (Account.name.ilike(f"%{search}%")) |
            (Account.account_number.ilike(f"%{search}%"))
        )
    accounts = q.order_by(Account.account_number).all()
    return [_serialize_account(a) for a in accounts]


@router.post("/accounts")
def create_account(data: dict = Body(...), user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    org_id = _get_user_org(db, user)
    account = Account(
        org_id=org_id,
        account_number=data["account_number"],
        name=data["name"],
        account_type=data["account_type"],
        parent_id=data.get("parent_id"),
        description=data.get("description"),
        is_active=data.get("is_active", True),
        normal_balance=data.get("normal_balance", "debit"),
        balance=float(data.get("balance", 0)),
    )
    db.add(account)
    db.commit()
    db.refresh(account)
    return _serialize_account(account)


@router.get("/accounts/{account_id}")
def get_account(account_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    org_id = _get_user_org(db, user)
    account = db.query(Account).filter(Account.id == account_id, Account.org_id == org_id).first()
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")
    return _serialize_account(account)


@router.put("/accounts/{account_id}")
def update_account(account_id: str, data: dict = Body(...), user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    org_id = _get_user_org(db, user)
    account = db.query(Account).filter(Account.id == account_id, Account.org_id == org_id).first()
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")
    fields = ["account_number", "name", "description", "normal_balance", "parent_id"]
    for f in fields:
        if f in data:
            setattr(account, f, data[f])
    if "account_type" in data:
        account.account_type = data["account_type"]
    if "is_active" in data:
        account.is_active = data["is_active"]
    if "balance" in data:
        account.balance = float(data["balance"])
    db.commit()
    db.refresh(account)
    return _serialize_account(account)


@router.delete("/accounts/{account_id}")
def delete_account(account_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    org_id = _get_user_org(db, user)
    account = db.query(Account).filter(Account.id == account_id, Account.org_id == org_id).first()
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")
    line_count = db.query(func.count(JournalEntryLine.id)).filter(JournalEntryLine.account_id == account_id).scalar() or 0
    if line_count > 0:
        raise HTTPException(status_code=400, detail="Cannot delete account with journal entry lines")
    db.delete(account)
    db.commit()
    return {"ok": True, "id": str(account_id)}


@router.get("/journal-entries")
def list_journal_entries(
    is_posted: bool = Query(None),
    start_date: str = Query(None),
    end_date: str = Query(None),
    search: str = Query(None),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    org_id = _get_user_org(db, user)
    q = db.query(JournalEntry).filter(JournalEntry.org_id == org_id)
    if is_posted is not None:
        q = q.filter(JournalEntry.is_posted == is_posted)
    if start_date:
        q = q.filter(JournalEntry.entry_date >= datetime.fromisoformat(start_date))
    if end_date:
        q = q.filter(JournalEntry.entry_date <= datetime.fromisoformat(end_date))
    if search:
        q = q.filter(
            (JournalEntry.entry_number.ilike(f"%{search}%")) |
            (JournalEntry.description.ilike(f"%{search}%"))
        )
    entries = q.order_by(desc(JournalEntry.entry_date)).all()
    return [_serialize_journal_entry(je) for je in entries]


@router.post("/journal-entries")
def create_journal_entry(data: dict = Body(...), user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    org_id = _get_user_org(db, user)
    lines_data = data.get("lines", [])
    if not lines_data:
        raise HTTPException(status_code=400, detail="Journal entry must have at least one line")

    total_debit = sum(float(l.get("debit", 0)) for l in lines_data)
    total_credit = sum(float(l.get("credit", 0)) for l in lines_data)
    if round(total_debit, 2) != round(total_credit, 2):
        raise HTTPException(status_code=400, detail="Total debits must equal total credits")

    je = JournalEntry(
        org_id=org_id,
        entry_number=data["entry_number"],
        entry_date=datetime.fromisoformat(data["entry_date"]),
        description=data.get("description"),
        reference=data.get("reference"),
        source=data.get("source", "manual"),
        total_debit=total_debit,
        total_credit=total_credit,
        created_by=user.id,
    )
    db.add(je)
    db.flush()

    created_lines = []
    for ld in lines_data:
        line = JournalEntryLine(
            entry_id=je.id,
            account_id=ld["account_id"],
            description=ld.get("description"),
            debit=float(ld.get("debit", 0)),
            credit=float(ld.get("credit", 0)),
            project_id=ld.get("project_id"),
        )
        db.add(line)
        created_lines.append(line)

    db.commit()
    db.refresh(je)
    for line in created_lines:
        db.refresh(line)
    return _serialize_journal_entry(je, created_lines)


@router.get("/journal-entries/{entry_id}")
def get_journal_entry(entry_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    org_id = _get_user_org(db, user)
    je = db.query(JournalEntry).filter(JournalEntry.id == entry_id, JournalEntry.org_id == org_id).first()
    if not je:
        raise HTTPException(status_code=404, detail="Journal entry not found")
    lines = db.query(JournalEntryLine).filter(JournalEntryLine.entry_id == entry_id).all()
    return _serialize_journal_entry(je, lines)


@router.post("/journal-entries/{entry_id}/post")
def post_journal_entry(entry_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    org_id = _get_user_org(db, user)
    je = db.query(JournalEntry).filter(JournalEntry.id == entry_id, JournalEntry.org_id == org_id).first()
    if not je:
        raise HTTPException(status_code=404, detail="Journal entry not found")
    if je.is_posted:
        raise HTTPException(status_code=400, detail="Journal entry already posted")

    lines = db.query(JournalEntryLine).filter(JournalEntryLine.entry_id == entry_id).all()
    if not lines:
        raise HTTPException(status_code=400, detail="Cannot post entry with no lines")

    for line in lines:
        account = db.query(Account).filter(Account.id == line.account_id).first()
        if account:
            account.balance = float(account.balance or 0) + float(line.debit or 0) - float(line.credit or 0)

    je.is_posted = True
    je.posted_at = datetime.utcnow()
    je.approved_by = user.id
    db.commit()
    db.refresh(je)
    return _serialize_journal_entry(je, lines)


@router.get("/payables")
def list_accounts_payable(
    status: str = Query(None),
    search: str = Query(None),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    org_id = _get_user_org(db, user)
    q = db.query(AccountsPayable).filter(AccountsPayable.org_id == org_id)
    if status:
        q = q.filter(AccountsPayable.status == status)
    if search:
        q = q.filter(
            (AccountsPayable.vendor_name.ilike(f"%{search}%")) |
            (AccountsPayable.invoice_number.ilike(f"%{search}%"))
        )
    items = q.order_by(desc(AccountsPayable.due_date)).all()
    return [_serialize_ap(ap) for ap in items]


@router.post("/payables")
def create_accounts_payable(data: dict = Body(...), user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    org_id = _get_user_org(db, user)
    ap = AccountsPayable(
        org_id=org_id,
        vendor_name=data["vendor_name"],
        vendor_contact=data.get("vendor_contact"),
        invoice_number=data["invoice_number"],
        invoice_date=datetime.fromisoformat(data["invoice_date"]),
        due_date=datetime.fromisoformat(data["due_date"]),
        amount=float(data["amount"]),
        amount_paid=float(data.get("amount_paid", 0)),
        status=data.get("status", APStatus.PENDING.value),
        account_id=data.get("account_id"),
        project_id=data.get("project_id"),
        description=data.get("description"),
        payment_terms=data.get("payment_terms"),
        payment_method=data.get("payment_method"),
        created_by=user.id,
    )
    db.add(ap)
    db.commit()
    db.refresh(ap)
    return _serialize_ap(ap)


@router.put("/payables/{payable_id}")
def update_accounts_payable(payable_id: str, data: dict = Body(...), user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    org_id = _get_user_org(db, user)
    ap = db.query(AccountsPayable).filter(AccountsPayable.id == payable_id, AccountsPayable.org_id == org_id).first()
    if not ap:
        raise HTTPException(status_code=404, detail="Accounts payable not found")
    fields = ["vendor_name", "vendor_contact", "invoice_number", "description",
              "payment_terms", "payment_method", "account_id", "project_id"]
    for f in fields:
        if f in data:
            setattr(ap, f, data[f])
    if "amount" in data:
        ap.amount = float(data["amount"])
    if "amount_paid" in data:
        ap.amount_paid = float(data["amount_paid"])
    if "status" in data:
        ap.status = data["status"]
    date_fields = ["invoice_date", "due_date", "paid_date"]
    for f in date_fields:
        if f in data:
            setattr(ap, f, datetime.fromisoformat(data[f]) if data[f] else None)
    db.commit()
    db.refresh(ap)
    return _serialize_ap(ap)


@router.post("/payables/{payable_id}/pay")
def pay_accounts_payable(payable_id: str, data: dict = Body(...), user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    org_id = _get_user_org(db, user)
    ap = db.query(AccountsPayable).filter(AccountsPayable.id == payable_id, AccountsPayable.org_id == org_id).first()
    if not ap:
        raise HTTPException(status_code=404, detail="Accounts payable not found")
    payment_amount = float(data.get("amount", 0))
    if payment_amount <= 0:
        raise HTTPException(status_code=400, detail="Payment amount must be positive")
    ap.amount_paid = float(ap.amount_paid or 0) + payment_amount
    ap.payment_method = data.get("payment_method", ap.payment_method)
    if ap.amount_paid >= ap.amount:
        ap.status = APStatus.PAID
        ap.paid_date = datetime.utcnow()
    else:
        ap.status = APStatus.APPROVED
    db.commit()
    db.refresh(ap)
    return _serialize_ap(ap)


@router.get("/receivables")
def list_accounts_receivable(
    status: str = Query(None),
    search: str = Query(None),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    org_id = _get_user_org(db, user)
    q = db.query(AccountsReceivable).filter(AccountsReceivable.org_id == org_id)
    if status:
        q = q.filter(AccountsReceivable.status == status)
    if search:
        q = q.filter(
            (AccountsReceivable.customer_name.ilike(f"%{search}%")) |
            (AccountsReceivable.invoice_number.ilike(f"%{search}%"))
        )
    items = q.order_by(desc(AccountsReceivable.due_date)).all()
    return [_serialize_ar(ar) for ar in items]


@router.post("/receivables")
def create_accounts_receivable(data: dict = Body(...), user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    org_id = _get_user_org(db, user)
    ar = AccountsReceivable(
        org_id=org_id,
        customer_name=data["customer_name"],
        customer_contact=data.get("customer_contact"),
        invoice_id=data.get("invoice_id"),
        invoice_number=data["invoice_number"],
        invoice_date=datetime.fromisoformat(data["invoice_date"]),
        due_date=datetime.fromisoformat(data["due_date"]),
        amount=float(data["amount"]),
        amount_received=float(data.get("amount_received", 0)),
        status=data.get("status", ARStatus.OUTSTANDING.value),
        account_id=data.get("account_id"),
        project_id=data.get("project_id"),
        description=data.get("description"),
        payment_terms=data.get("payment_terms"),
        created_by=user.id,
    )
    db.add(ar)
    db.commit()
    db.refresh(ar)
    return _serialize_ar(ar)


@router.put("/receivables/{receivable_id}")
def update_accounts_receivable(receivable_id: str, data: dict = Body(...), user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    org_id = _get_user_org(db, user)
    ar = db.query(AccountsReceivable).filter(AccountsReceivable.id == receivable_id, AccountsReceivable.org_id == org_id).first()
    if not ar:
        raise HTTPException(status_code=404, detail="Accounts receivable not found")
    fields = ["customer_name", "customer_contact", "invoice_number", "description",
              "payment_terms", "account_id", "project_id", "invoice_id"]
    for f in fields:
        if f in data:
            setattr(ar, f, data[f])
    if "amount" in data:
        ar.amount = float(data["amount"])
    if "amount_received" in data:
        ar.amount_received = float(data["amount_received"])
    if "status" in data:
        ar.status = data["status"]
    date_fields = ["invoice_date", "due_date", "last_payment_date"]
    for f in date_fields:
        if f in data:
            setattr(ar, f, datetime.fromisoformat(data[f]) if data[f] else None)
    db.commit()
    db.refresh(ar)
    return _serialize_ar(ar)


@router.post("/receivables/{receivable_id}/receive")
def receive_accounts_receivable(receivable_id: str, data: dict = Body(...), user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    org_id = _get_user_org(db, user)
    ar = db.query(AccountsReceivable).filter(AccountsReceivable.id == receivable_id, AccountsReceivable.org_id == org_id).first()
    if not ar:
        raise HTTPException(status_code=404, detail="Accounts receivable not found")
    receipt_amount = float(data.get("amount", 0))
    if receipt_amount <= 0:
        raise HTTPException(status_code=400, detail="Receipt amount must be positive")
    ar.amount_received = float(ar.amount_received or 0) + receipt_amount
    ar.last_payment_date = datetime.utcnow()
    if ar.amount_received >= ar.amount:
        ar.status = ARStatus.PAID
    else:
        ar.status = ARStatus.PARTIAL
    db.commit()
    db.refresh(ar)
    return _serialize_ar(ar)


@router.get("/financial-statements")
def get_financial_statements(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    org_id = _get_user_org(db, user)
    accounts = db.query(Account).filter(Account.org_id == org_id, Account.is_active == True).order_by(Account.account_number).all()

    assets = []
    liabilities = []
    equity = []
    revenue = []
    expenses = []

    total_assets = 0
    total_liabilities = 0
    total_equity = 0
    total_revenue = 0
    total_expenses = 0

    for a in accounts:
        entry = {"account_number": a.account_number, "name": a.name, "balance": float(a.balance or 0)}
        if a.account_type == AccountType.ASSET:
            assets.append(entry)
            total_assets += entry["balance"]
        elif a.account_type == AccountType.LIABILITY:
            liabilities.append(entry)
            total_liabilities += entry["balance"]
        elif a.account_type == AccountType.EQUITY:
            equity.append(entry)
            total_equity += entry["balance"]
        elif a.account_type == AccountType.REVENUE:
            revenue.append(entry)
            total_revenue += entry["balance"]
        elif a.account_type == AccountType.EXPENSE:
            expenses.append(entry)
            total_expenses += entry["balance"]

    net_income = total_revenue - total_expenses

    return {
        "profit_and_loss": {
            "revenue": revenue,
            "total_revenue": round(total_revenue, 2),
            "expenses": expenses,
            "total_expenses": round(total_expenses, 2),
            "net_income": round(net_income, 2),
        },
        "balance_sheet": {
            "assets": assets,
            "total_assets": round(total_assets, 2),
            "liabilities": liabilities,
            "total_liabilities": round(total_liabilities, 2),
            "equity": equity,
            "total_equity": round(total_equity, 2),
            "retained_earnings": round(net_income, 2),
            "total_liabilities_and_equity": round(total_liabilities + total_equity + net_income, 2),
        },
        "generated_at": datetime.utcnow().isoformat(),
    }


@router.get("/trial-balance")
def get_trial_balance(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    org_id = _get_user_org(db, user)
    accounts = db.query(Account).filter(Account.org_id == org_id, Account.is_active == True).order_by(Account.account_number).all()

    rows = []
    total_debits = 0
    total_credits = 0

    for a in accounts:
        balance = float(a.balance or 0)
        debit = 0.0
        credit = 0.0
        if a.normal_balance == "debit":
            if balance >= 0:
                debit = balance
            else:
                credit = abs(balance)
        else:
            if balance >= 0:
                credit = balance
            else:
                debit = abs(balance)
        total_debits += debit
        total_credits += credit
        rows.append({
            "account_number": a.account_number,
            "name": a.name,
            "account_type": a.account_type.value if a.account_type else None,
            "debit": round(debit, 2),
            "credit": round(credit, 2),
        })

    return {
        "rows": rows,
        "total_debits": round(total_debits, 2),
        "total_credits": round(total_credits, 2),
        "is_balanced": round(total_debits, 2) == round(total_credits, 2),
        "generated_at": datetime.utcnow().isoformat(),
    }
