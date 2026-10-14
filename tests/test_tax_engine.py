"""Boundary and property checks for the tax rules."""

from datetime import date
from decimal import Decimal

import pytest
from hypothesis import given, strategies as st

from src.tax_engine import (
    CorporateIncomeTax,
    InvalidIncomeError,
    Money,
    NoScheduleForDateError,
    PAYE,
    SupplyType,
    TaxContext,
    VAT,
    Invoice,
)


def resident_tax(income: int) -> Decimal:
    return PAYE().calculate(TaxContext(amount=Money.of(income))).amount.amount


def test_every_resident_band_edge() -> None:
    expected = {
        335_000: Decimal("0"),
        335_001: Decimal("0"),
        410_000: Decimal("15000"),
        485_000: Decimal("33750"),
        10_000_000: Decimal("2888250"),
        10_000_001: Decimal("2888250"),
    }
    assert {income: resident_tax(income) for income in expected} == expected


def test_nonresident_has_no_tax_free_threshold() -> None:
    calculator = PAYE()
    expected = {
        335_000: Decimal("33500"),
        410_000: Decimal("48500"),
        485_000: Decimal("67250"),
        10_000_000: Decimal("2921750"),
    }
    assert {
        income: calculator.calculate(
            TaxContext(amount=Money.of(income), resident=False)
        ).amount.amount
        for income in expected
    } == expected


def test_money_rounds_and_rejects_floats() -> None:
    assert Money.of("2.5") == Money.of(3)
    with pytest.raises(TypeError):
        Money.of(0.1)


def test_vat_supply_types_and_corporate_tax() -> None:
    invoices = (
        Invoice(Money.of(100_000)),
        Invoice(Money.of(50_000), SupplyType.ZERO_RATED),
        Invoice(Money.of(75_000), SupplyType.EXEMPT),
        Invoice(Money.of(20_000), is_purchase=True),
    )
    vat = VAT().calculate(TaxContext(invoices=invoices))
    assert vat.breakdown["output_vat"] == Money.of(18_000)
    assert vat.breakdown["input_vat"] == Money.of(3_600)
    assert vat.amount == Money.of(14_400)
    corporate = CorporateIncomeTax().calculate(
        TaxContext(amount=Money.of(1_000_000), deductions=Money.of(200_000))
    )
    assert corporate.amount == Money.of(240_000)


def test_missing_historical_schedule_is_explicit() -> None:
    with pytest.raises(NoScheduleForDateError):
        PAYE().calculate(TaxContext(amount=Money.of(500_000), effective_date=date(2025, 7, 1)))


@given(st.integers(min_value=0, max_value=100_000_000))
def test_paye_is_nonnegative_and_never_exceeds_income(income: int) -> None:
    tax = resident_tax(income)
    assert tax >= 0
    assert tax <= income


@given(
    st.integers(min_value=0, max_value=100_000_000),
    st.integers(min_value=0, max_value=100_000_000),
)
def test_paye_is_monotonic(income: int, increase: int) -> None:
    assert resident_tax(income + increase) >= resident_tax(income)
