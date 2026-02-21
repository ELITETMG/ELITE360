import uuid
from datetime import datetime, timedelta
from collections import defaultdict
from fastapi import APIRouter, Depends, HTTPException, Query, Body
from sqlalchemy.orm import Session
from sqlalchemy import func, desc, extract
from app.db.session import get_db
from app.core.auth import get_current_user
from app.models.models import (
    PayPeriod, PayPeriodType, PayRun, PayRunStatus, PayStub, PayDeduction,
    TaxWithholding, CompensationRecord, TimeEntry, EmployeeProfile,
    EmployeeStatus, OrgMember, User
)

router = APIRouter(prefix="/api/payroll", tags=["payroll"])


def _get_user_org(db: Session, user: User):
    membership = db.query(OrgMember).filter(OrgMember.user_id == user.id).first()
    if not membership:
        raise HTTPException(status_code=403, detail="No org membership")
    return membership.org_id


FEDERAL_BRACKETS_2025 = [
    (11600, 0.10),
    (47150, 0.12),
    (100525, 0.22),
    (191950, 0.24),
    (243725, 0.32),
    (609350, 0.35),
    (float("inf"), 0.37),
]

SS_RATE = 0.062
SS_WAGE_BASE = 168600
MEDICARE_RATE = 0.0145
MEDICARE_ADDITIONAL_RATE = 0.009
MEDICARE_ADDITIONAL_THRESHOLD = 200000
STATE_TAX_RATE = 0.05
FUTA_RATE = 0.006
FUTA_WAGE_BASE = 7000


def _calc_federal_tax(annual_gross: float) -> float:
    tax = 0.0
    prev = 0
    for bracket_top, rate in FEDERAL_BRACKETS_2025:
        if annual_gross <= prev:
            break
        taxable = min(annual_gross, bracket_top) - prev
        tax += taxable * rate
        prev = bracket_top
    return round(tax, 2)


def _calc_fica(gross: float, ytd_gross: float = 0):
    ss_remaining = max(SS_WAGE_BASE - ytd_gross, 0)
    ss_taxable = min(gross, ss_remaining)
    ss = round(ss_taxable * SS_RATE, 2)
    medicare = round(gross * MEDICARE_RATE, 2)
    if (ytd_gross + gross) > MEDICARE_ADDITIONAL_THRESHOLD:
        additional_base = max((ytd_gross + gross) - MEDICARE_ADDITIONAL_THRESHOLD, 0)
        already_additional = max(ytd_gross - MEDICARE_ADDITIONAL_THRESHOLD, 0)
        medicare += round((additional_base - already_additional) * MEDICARE_ADDITIONAL_RATE, 2)
    return ss, medicare


def _calc_futa(gross: float, ytd_gross: float = 0):
    remaining = max(FUTA_WAGE_BASE - ytd_gross, 0)
    taxable = min(gross, remaining)
    return round(taxable * FUTA_RATE, 2)


def _serialize_pay_period(pp):
    return {
        "id": pp.id,
        "org_id": pp.org_id,
        "period_type": pp.period_type.value if pp.period_type else None,
        "start_date": str(pp.start_date) if pp.start_date else None,
        "end_date": str(pp.end_date) if pp.end_date else None,
        "pay_date": str(pp.pay_date) if pp.pay_date else None,
        "is_closed": pp.is_closed,
        "created_at": str(pp.created_at) if pp.created_at else None,
    }


def _serialize_pay_run(pr):
    return {
        "id": pr.id,
        "org_id": pr.org_id,
        "pay_period_id": pr.pay_period_id,
        "run_number": pr.run_number,
        "status": pr.status.value if pr.status else None,
        "total_gross": float(pr.total_gross or 0),
        "total_deductions": float(pr.total_deductions or 0),
        "total_taxes": float(pr.total_taxes or 0),
        "total_net": float(pr.total_net or 0),
        "employee_count": pr.employee_count or 0,
        "processed_by": pr.processed_by,
        "approved_by": pr.approved_by,
        "processed_at": str(pr.processed_at) if pr.processed_at else None,
        "approved_at": str(pr.approved_at) if pr.approved_at else None,
        "notes": pr.notes,
        "created_at": str(pr.created_at) if pr.created_at else None,
    }


def _serialize_pay_stub(ps, include_details=False, db=None):
    data = {
        "id": ps.id,
        "org_id": ps.org_id,
        "pay_run_id": ps.pay_run_id,
        "user_id": ps.user_id,
        "employee_name": ps.user.full_name if ps.user else None,
        "regular_hours": float(ps.regular_hours or 0),
        "overtime_hours": float(ps.overtime_hours or 0),
        "holiday_hours": float(ps.holiday_hours or 0),
        "pto_hours": float(ps.pto_hours or 0),
        "regular_pay": float(ps.regular_pay or 0),
        "overtime_pay": float(ps.overtime_pay or 0),
        "holiday_pay": float(ps.holiday_pay or 0),
        "pto_pay": float(ps.pto_pay or 0),
        "bonus": float(ps.bonus or 0),
        "per_diem": float(ps.per_diem or 0),
        "gross_pay": float(ps.gross_pay or 0),
        "total_deductions": float(ps.total_deductions or 0),
        "total_taxes": float(ps.total_taxes or 0),
        "net_pay": float(ps.net_pay or 0),
        "ytd_gross": float(ps.ytd_gross or 0),
        "ytd_taxes": float(ps.ytd_taxes or 0),
        "ytd_net": float(ps.ytd_net or 0),
        "created_at": str(ps.created_at) if ps.created_at else None,
    }
    if include_details and db:
        deductions = db.query(PayDeduction).filter(PayDeduction.pay_stub_id == ps.id).all()
        taxes = db.query(TaxWithholding).filter(TaxWithholding.pay_stub_id == ps.id).all()
        data["deductions"] = [{
            "id": d.id,
            "deduction_type": d.deduction_type,
            "description": d.description,
            "amount": float(d.amount or 0),
            "is_pretax": d.is_pretax,
        } for d in deductions]
        data["taxes"] = [{
            "id": t.id,
            "tax_type": t.tax_type,
            "description": t.description,
            "taxable_amount": float(t.taxable_amount or 0),
            "rate": float(t.rate or 0),
            "amount": float(t.amount or 0),
        } for t in taxes]
    return data


@router.get("/stats")
def get_payroll_stats(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    org_id = _get_user_org(db, user)
    now = datetime.utcnow()
    year_start = now.replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0)

    active_employees = db.query(func.count(EmployeeProfile.id)).filter(
        EmployeeProfile.org_id == org_id,
        EmployeeProfile.status == EmployeeStatus.ACTIVE
    ).scalar() or 0

    current_period = db.query(PayPeriod).filter(
        PayPeriod.org_id == org_id,
        PayPeriod.start_date <= now,
        PayPeriod.end_date >= now
    ).first()

    ytd_gross = db.query(func.coalesce(func.sum(PayStub.gross_pay), 0)).filter(
        PayStub.org_id == org_id,
        PayStub.created_at >= year_start
    ).scalar() or 0

    ytd_taxes = db.query(func.coalesce(func.sum(PayStub.total_taxes), 0)).filter(
        PayStub.org_id == org_id,
        PayStub.created_at >= year_start
    ).scalar() or 0

    ytd_net = db.query(func.coalesce(func.sum(PayStub.net_pay), 0)).filter(
        PayStub.org_id == org_id,
        PayStub.created_at >= year_start
    ).scalar() or 0

    pending_runs = db.query(func.count(PayRun.id)).filter(
        PayRun.org_id == org_id,
        PayRun.status.in_([PayRunStatus.DRAFT, PayRunStatus.PROCESSING])
    ).scalar() or 0

    total_runs = db.query(func.count(PayRun.id)).filter(
        PayRun.org_id == org_id,
        PayRun.created_at >= year_start
    ).scalar() or 0

    return {
        "active_employees": active_employees,
        "current_period": _serialize_pay_period(current_period) if current_period else None,
        "total_payroll_ytd": round(float(ytd_gross), 2),
        "total_taxes_ytd": round(float(ytd_taxes), 2),
        "total_net_ytd": round(float(ytd_net), 2),
        "pending_pay_runs": pending_runs,
        "total_pay_runs_ytd": total_runs,
    }


@router.get("/pay-periods")
def list_pay_periods(
    period_type: str = Query(None),
    is_closed: bool = Query(None),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    org_id = _get_user_org(db, user)
    q = db.query(PayPeriod).filter(PayPeriod.org_id == org_id)
    if period_type:
        q = q.filter(PayPeriod.period_type == period_type)
    if is_closed is not None:
        q = q.filter(PayPeriod.is_closed == is_closed)
    periods = q.order_by(desc(PayPeriod.start_date)).all()
    return [_serialize_pay_period(pp) for pp in periods]


@router.post("/pay-periods")
def create_pay_period(data: dict = Body(...), user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    org_id = _get_user_org(db, user)
    pp = PayPeriod(
        org_id=org_id,
        period_type=data.get("period_type", "biweekly"),
        start_date=datetime.fromisoformat(data["start_date"]),
        end_date=datetime.fromisoformat(data["end_date"]),
        pay_date=datetime.fromisoformat(data["pay_date"]),
        is_closed=data.get("is_closed", False),
    )
    db.add(pp)
    db.commit()
    db.refresh(pp)
    return _serialize_pay_period(pp)


@router.put("/pay-periods/{period_id}")
def update_pay_period(period_id: str, data: dict = Body(...), user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    org_id = _get_user_org(db, user)
    pp = db.query(PayPeriod).filter(PayPeriod.id == period_id, PayPeriod.org_id == org_id).first()
    if not pp:
        raise HTTPException(status_code=404, detail="Pay period not found")
    if "period_type" in data:
        pp.period_type = data["period_type"]
    if "start_date" in data:
        pp.start_date = datetime.fromisoformat(data["start_date"])
    if "end_date" in data:
        pp.end_date = datetime.fromisoformat(data["end_date"])
    if "pay_date" in data:
        pp.pay_date = datetime.fromisoformat(data["pay_date"])
    if "is_closed" in data:
        pp.is_closed = data["is_closed"]
    db.commit()
    db.refresh(pp)
    return _serialize_pay_period(pp)


@router.get("/pay-runs")
def list_pay_runs(
    pay_period_id: str = Query(None),
    status: str = Query(None),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    org_id = _get_user_org(db, user)
    q = db.query(PayRun).filter(PayRun.org_id == org_id)
    if pay_period_id:
        q = q.filter(PayRun.pay_period_id == pay_period_id)
    if status:
        q = q.filter(PayRun.status == status)
    runs = q.order_by(desc(PayRun.created_at)).all()
    return [_serialize_pay_run(pr) for pr in runs]


@router.post("/pay-runs")
def create_pay_run(data: dict = Body(...), user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    org_id = _get_user_org(db, user)
    pay_period_id = data.get("pay_period_id")
    if not pay_period_id:
        raise HTTPException(status_code=400, detail="pay_period_id is required")
    pp = db.query(PayPeriod).filter(PayPeriod.id == pay_period_id, PayPeriod.org_id == org_id).first()
    if not pp:
        raise HTTPException(status_code=404, detail="Pay period not found")

    existing_count = db.query(func.count(PayRun.id)).filter(
        PayRun.org_id == org_id, PayRun.pay_period_id == pay_period_id
    ).scalar() or 0
    run_number = f"PR-{pp.start_date.strftime('%Y%m%d')}-{existing_count + 1}"

    pr = PayRun(
        org_id=org_id,
        pay_period_id=pay_period_id,
        run_number=run_number,
        status=PayRunStatus.DRAFT,
        notes=data.get("notes"),
    )
    db.add(pr)
    db.commit()
    db.refresh(pr)
    return _serialize_pay_run(pr)


@router.get("/pay-runs/{run_id}")
def get_pay_run(run_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    org_id = _get_user_org(db, user)
    pr = db.query(PayRun).filter(PayRun.id == run_id, PayRun.org_id == org_id).first()
    if not pr:
        raise HTTPException(status_code=404, detail="Pay run not found")
    result = _serialize_pay_run(pr)
    stubs = db.query(PayStub).filter(PayStub.pay_run_id == run_id).all()
    result["pay_stubs"] = [_serialize_pay_stub(ps) for ps in stubs]
    return result


@router.post("/pay-runs/{run_id}/process")
def process_pay_run(run_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    org_id = _get_user_org(db, user)
    pr = db.query(PayRun).filter(PayRun.id == run_id, PayRun.org_id == org_id).first()
    if not pr:
        raise HTTPException(status_code=404, detail="Pay run not found")
    if pr.status not in (PayRunStatus.DRAFT,):
        raise HTTPException(status_code=400, detail="Pay run can only be processed from draft status")
    pr.status = PayRunStatus.PROCESSING
    pr.processed_by = user.id
    pr.processed_at = datetime.utcnow()
    db.commit()
    db.refresh(pr)
    return _serialize_pay_run(pr)


@router.post("/pay-runs/{run_id}/approve")
def approve_pay_run(run_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    org_id = _get_user_org(db, user)
    pr = db.query(PayRun).filter(PayRun.id == run_id, PayRun.org_id == org_id).first()
    if not pr:
        raise HTTPException(status_code=404, detail="Pay run not found")
    if pr.status not in (PayRunStatus.PROCESSING,):
        raise HTTPException(status_code=400, detail="Pay run can only be approved from processing status")
    pr.status = PayRunStatus.APPROVED
    pr.approved_by = user.id
    pr.approved_at = datetime.utcnow()
    db.commit()
    db.refresh(pr)
    return _serialize_pay_run(pr)


@router.get("/pay-stubs")
def list_pay_stubs(
    pay_run_id: str = Query(None),
    user_id: str = Query(None),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    org_id = _get_user_org(db, user)
    q = db.query(PayStub).filter(PayStub.org_id == org_id)
    if pay_run_id:
        q = q.filter(PayStub.pay_run_id == pay_run_id)
    if user_id:
        q = q.filter(PayStub.user_id == user_id)
    stubs = q.order_by(desc(PayStub.created_at)).all()
    return [_serialize_pay_stub(ps) for ps in stubs]


@router.get("/pay-stubs/{stub_id}")
def get_pay_stub(stub_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    org_id = _get_user_org(db, user)
    ps = db.query(PayStub).filter(PayStub.id == stub_id, PayStub.org_id == org_id).first()
    if not ps:
        raise HTTPException(status_code=404, detail="Pay stub not found")
    return _serialize_pay_stub(ps, include_details=True, db=db)


@router.get("/employee/{user_id}/history")
def get_employee_pay_history(user_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    org_id = _get_user_org(db, user)
    member = db.query(OrgMember).filter(OrgMember.org_id == org_id, OrgMember.user_id == user_id).first()
    if not member:
        raise HTTPException(status_code=404, detail="Employee not found in organization")

    stubs = db.query(PayStub).filter(
        PayStub.org_id == org_id,
        PayStub.user_id == user_id
    ).order_by(desc(PayStub.created_at)).all()

    comp_records = db.query(CompensationRecord).filter(
        CompensationRecord.org_id == org_id,
        CompensationRecord.user_id == user_id
    ).order_by(desc(CompensationRecord.effective_date)).all()

    emp_user = db.query(User).filter(User.id == user_id).first()

    return {
        "user_id": user_id,
        "employee_name": emp_user.full_name if emp_user else None,
        "pay_stubs": [_serialize_pay_stub(ps) for ps in stubs],
        "compensation_records": [{
            "id": cr.id,
            "pay_type": cr.pay_type,
            "hourly_rate": float(cr.hourly_rate) if cr.hourly_rate else None,
            "salary": float(cr.salary) if cr.salary else None,
            "overtime_rate": float(cr.overtime_rate) if cr.overtime_rate else None,
            "per_diem": float(cr.per_diem) if cr.per_diem else None,
            "effective_date": str(cr.effective_date) if cr.effective_date else None,
            "end_date": str(cr.end_date) if cr.end_date else None,
            "is_current": cr.is_current,
            "reason": cr.reason,
        } for cr in comp_records],
    }


@router.post("/calculate-payroll")
def calculate_payroll(data: dict = Body(...), user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    org_id = _get_user_org(db, user)
    pay_run_id = data.get("pay_run_id")
    if not pay_run_id:
        raise HTTPException(status_code=400, detail="pay_run_id is required")

    pr = db.query(PayRun).filter(PayRun.id == pay_run_id, PayRun.org_id == org_id).first()
    if not pr:
        raise HTTPException(status_code=404, detail="Pay run not found")

    pp = db.query(PayPeriod).filter(PayPeriod.id == pr.pay_period_id).first()
    if not pp:
        raise HTTPException(status_code=404, detail="Pay period not found")

    comp_records = db.query(CompensationRecord).filter(
        CompensationRecord.org_id == org_id,
        CompensationRecord.is_current == True
    ).all()

    if not comp_records:
        raise HTTPException(status_code=400, detail="No active compensation records found")

    year_start = pp.start_date.replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0)

    periods_per_year = {"weekly": 52, "biweekly": 26, "semimonthly": 24, "monthly": 12}
    period_type_val = pp.period_type.value if hasattr(pp.period_type, 'value') else str(pp.period_type)
    pay_periods_count = periods_per_year.get(period_type_val, 26)

    total_gross = 0
    total_deductions = 0
    total_taxes = 0
    total_net = 0
    employee_count = 0
    results = []

    for comp in comp_records:
        time_entries = db.query(TimeEntry).filter(
            TimeEntry.org_id == org_id,
            TimeEntry.user_id == comp.user_id,
            TimeEntry.clock_in >= pp.start_date,
            TimeEntry.clock_in <= pp.end_date,
            TimeEntry.total_hours.isnot(None)
        ).all()

        total_hours = sum(float(te.total_hours or 0) for te in time_entries)

        weekly_hours = defaultdict(float)
        for te in time_entries:
            week_key = te.clock_in.isocalendar()[1]
            weekly_hours[week_key] += float(te.total_hours or 0)

        regular_hours = 0.0
        overtime_hours = 0.0
        for week, hours in weekly_hours.items():
            if hours > 40:
                regular_hours += 40
                overtime_hours += hours - 40
            else:
                regular_hours += hours

        hourly_rate = float(comp.hourly_rate or 0)
        overtime_rate = float(comp.overtime_rate or 0) if comp.overtime_rate else hourly_rate * 1.5

        if comp.pay_type == "salary" and comp.salary:
            regular_pay = round(float(comp.salary) / pay_periods_count, 2)
            overtime_pay = round(overtime_hours * overtime_rate, 2)
        else:
            regular_pay = round(regular_hours * hourly_rate, 2)
            overtime_pay = round(overtime_hours * overtime_rate, 2)

        per_diem_amount = float(comp.per_diem or 0)
        gross_pay = round(regular_pay + overtime_pay + per_diem_amount, 2)

        prev_stubs = db.query(PayStub).filter(
            PayStub.org_id == org_id,
            PayStub.user_id == comp.user_id,
            PayStub.created_at >= year_start,
            PayStub.pay_run_id != pay_run_id
        ).all()
        ytd_gross_prev = sum(float(s.gross_pay or 0) for s in prev_stubs)
        ytd_taxes_prev = sum(float(s.total_taxes or 0) for s in prev_stubs)
        ytd_net_prev = sum(float(s.net_pay or 0) for s in prev_stubs)

        annual_gross_estimate = gross_pay * pay_periods_count
        federal_annual = _calc_federal_tax(annual_gross_estimate)
        federal_per_period = round(federal_annual / pay_periods_count, 2)

        state_tax = round(gross_pay * STATE_TAX_RATE, 2)

        ss_tax, medicare_tax = _calc_fica(gross_pay, ytd_gross_prev)

        futa_tax = _calc_futa(gross_pay, ytd_gross_prev)

        total_tax = round(federal_per_period + state_tax + ss_tax + medicare_tax + futa_tax, 2)
        net_pay = round(gross_pay - total_tax, 2)

        existing_stub = db.query(PayStub).filter(
            PayStub.pay_run_id == pay_run_id,
            PayStub.user_id == comp.user_id
        ).first()
        if existing_stub:
            db.query(TaxWithholding).filter(TaxWithholding.pay_stub_id == existing_stub.id).delete()
            db.query(PayDeduction).filter(PayDeduction.pay_stub_id == existing_stub.id).delete()
            db.delete(existing_stub)
            db.flush()

        stub = PayStub(
            org_id=org_id,
            pay_run_id=pay_run_id,
            user_id=comp.user_id,
            regular_hours=regular_hours,
            overtime_hours=overtime_hours,
            regular_pay=regular_pay,
            overtime_pay=overtime_pay,
            per_diem=per_diem_amount,
            gross_pay=gross_pay,
            total_deductions=0,
            total_taxes=total_tax,
            net_pay=net_pay,
            ytd_gross=round(ytd_gross_prev + gross_pay, 2),
            ytd_taxes=round(ytd_taxes_prev + total_tax, 2),
            ytd_net=round(ytd_net_prev + net_pay, 2),
        )
        db.add(stub)
        db.flush()

        tax_records = [
            TaxWithholding(org_id=org_id, pay_stub_id=stub.id, tax_type="federal",
                           description="Federal Income Tax", taxable_amount=gross_pay,
                           rate=round(federal_per_period / gross_pay, 4) if gross_pay > 0 else 0,
                           amount=federal_per_period),
            TaxWithholding(org_id=org_id, pay_stub_id=stub.id, tax_type="state",
                           description="State Income Tax", taxable_amount=gross_pay,
                           rate=STATE_TAX_RATE, amount=state_tax),
            TaxWithholding(org_id=org_id, pay_stub_id=stub.id, tax_type="social_security",
                           description="Social Security (OASDI)", taxable_amount=min(gross_pay, max(SS_WAGE_BASE - ytd_gross_prev, 0)),
                           rate=SS_RATE, amount=ss_tax),
            TaxWithholding(org_id=org_id, pay_stub_id=stub.id, tax_type="medicare",
                           description="Medicare", taxable_amount=gross_pay,
                           rate=MEDICARE_RATE, amount=medicare_tax),
            TaxWithholding(org_id=org_id, pay_stub_id=stub.id, tax_type="futa",
                           description="Federal Unemployment (FUTA)", taxable_amount=min(gross_pay, max(FUTA_WAGE_BASE - ytd_gross_prev, 0)),
                           rate=FUTA_RATE, amount=futa_tax),
        ]
        db.add_all(tax_records)

        employee_count += 1
        total_gross += gross_pay
        total_deductions += 0
        total_taxes += total_tax
        total_net += net_pay

        emp_user = db.query(User).filter(User.id == comp.user_id).first()
        results.append({
            "user_id": comp.user_id,
            "employee_name": emp_user.full_name if emp_user else None,
            "regular_hours": regular_hours,
            "overtime_hours": overtime_hours,
            "regular_pay": regular_pay,
            "overtime_pay": overtime_pay,
            "gross_pay": gross_pay,
            "total_taxes": total_tax,
            "net_pay": net_pay,
            "federal_tax": federal_per_period,
            "state_tax": state_tax,
            "social_security": ss_tax,
            "medicare": medicare_tax,
            "futa": futa_tax,
        })

    pr.total_gross = round(total_gross, 2)
    pr.total_deductions = round(total_deductions, 2)
    pr.total_taxes = round(total_taxes, 2)
    pr.total_net = round(total_net, 2)
    pr.employee_count = employee_count

    db.commit()

    return {
        "pay_run_id": pr.id,
        "run_number": pr.run_number,
        "employee_count": employee_count,
        "total_gross": round(total_gross, 2),
        "total_deductions": round(total_deductions, 2),
        "total_taxes": round(total_taxes, 2),
        "total_net": round(total_net, 2),
        "employees": results,
    }
