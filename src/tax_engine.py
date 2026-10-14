"""Small Decimal-only tax calculator for the assignment's Uganda baseline."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal, ROUND_HALF_UP
from enum import Enum

ZERO = Decimal("0")
CENT = Decimal("1")
SCHEDULE_START = date(2026, 7, 1)


class TaxError(Exception):
    """Base class for tax calculation errors."""


class InvalidIncomeError(TaxError, ValueError):
    """Raised when an income or deduction is invalid."""


class NoScheduleForDateError(TaxError):
    """Raised when no PAYE schedule covers the requested date."""


@dataclass(frozen=True)
class Money:
    """UGX amount rounded to whole shillings using half-up rounding."""

    amount: Decimal

    def __post_init__(self) -> None:
        if not isinstance(self.amount, Decimal):
            raise TypeError("Money requires decimal.Decimal; floats are not accepted")
        object.__setattr__(self, "amount", self.amount.quantize(CENT, rounding=ROUND_HALF_UP))

    @classmethod
    def of(cls, value: Decimal | int | str) -> Money:
        """Create UGX from an exact decimal, integer, or decimal string."""
        if isinstance(value, float):
            raise TypeError("Money does not accept floats")
        return cls(Decimal(value))

    def __add__(self, other: Money) -> Money:
        if not isinstance(other, Money):
            return NotImplemented
        return Money(self.amount + other.amount)

    def __mul__(self, rate: Decimal | int) -> Money:
        if isinstance(rate, float):
            raise TypeError("Money does not accept float rates")
        return Money(self.amount * Decimal(rate))

    def __lt__(self, other: Money) -> bool:
        if not isinstance(other, Money):
            return NotImplemented
        return self.amount < other.amount

    def __repr__(self) -> str:
        return f"UGX {self.amount:,.0f}"


ZERO_MONEY = Money.of(0)


class SupplyType(Enum):
    STANDARD = "standard"
    ZERO_RATED = "zero-rated"
    EXEMPT = "exempt"


@dataclass(frozen=True)
class Invoice:
    """An invoice amount before VAT; purchases may recover input VAT."""

    amount: Money
    supply: SupplyType = SupplyType.STANDARD
    is_purchase: bool = False


@dataclass(frozen=True)
class TaxContext:
    """Inputs shared by tax calculators; unused fields stay at their defaults."""

    amount: Money = ZERO_MONEY
    allowances: Money = ZERO_MONEY
    deductions: Money = ZERO_MONEY
    resident: bool = True
    effective_date: date = SCHEDULE_START
    invoices: tuple[Invoice, ...] = ()


@dataclass(frozen=True)
class TaxResult:
    """Tax due and a small breakdown suitable for display or payroll."""

    amount: Money
    breakdown: dict[str, Money] = field(default_factory=dict)


class Tax(ABC):
    """Common interface for the assignment's tax modules."""

    @abstractmethod
    def calculate(self, ctx: TaxContext) -> TaxResult:
        """Calculate tax from a typed context."""


class PAYE(Tax):
    """Monthly PAYE using the assignment's 2026/27 baseline bands."""

    def calculate(self, ctx: TaxContext) -> TaxResult:
        if ctx.effective_date < SCHEDULE_START:
            raise NoScheduleForDateError(f"No schedule configured for {ctx.effective_date}")
        taxable = ctx.amount.amount + ctx.allowances.amount - ctx.deductions.amount
        if taxable < ZERO:
            raise InvalidIncomeError("Allowances and income cannot be less than deductions")
        tax = self._resident_tax(taxable) if ctx.resident else self._nonresident_tax(taxable)
        return TaxResult(Money(tax), {"taxable_income": Money(taxable)})

    @staticmethod
    def _resident_tax(income: Decimal) -> Decimal:
        if income <= Decimal("335000"):
            return ZERO
        if income <= Decimal("410000"):
            return (income - Decimal("335000")) * Decimal("0.20")
        if income <= Decimal("485000"):
            return Decimal("15000") + (income - Decimal("410000")) * Decimal("0.25")
        if income <= Decimal("10000000"):
            return Decimal("33750") + (income - Decimal("485000")) * Decimal("0.30")
        return Decimal("2888250") + (income - Decimal("10000000")) * Decimal("0.40")

    @staticmethod
    def _nonresident_tax(income: Decimal) -> Decimal:
        if income <= Decimal("335000"):
            return income * Decimal("0.10")
        if income <= Decimal("410000"):
            return Decimal("33500") + (income - Decimal("335000")) * Decimal("0.20")
        if income <= Decimal("485000"):
            return Decimal("48500") + (income - Decimal("410000")) * Decimal("0.25")
        if income <= Decimal("10000000"):
            return Decimal("67250") + (income - Decimal("485000")) * Decimal("0.30")
        return Decimal("2921750") + (income - Decimal("10000000")) * Decimal("0.40")


class NSSF(Tax):
    """Employee and employer NSSF contributions on gross monthly pay."""

    def __init__(self, employee_rate: Decimal = Decimal("0.05"), employer_rate: Decimal = Decimal("0.10")) -> None:
        self.employee_rate = employee_rate
        self.employer_rate = employer_rate

    def calculate(self, ctx: TaxContext) -> TaxResult:
        self._validate_income(ctx.amount)
        return TaxResult(ctx.amount * self.employee_rate, {"employer": ctx.amount * self.employer_rate})

    @staticmethod
    def _validate_income(amount: Money) -> None:
        if amount.amount < ZERO:
            raise InvalidIncomeError("Income cannot be negative")


class LocalServiceTax(Tax):
    """Configurable monthly LST deduction applied before PAYE."""

    def __init__(self, monthly_amount: Money = ZERO_MONEY) -> None:
        if monthly_amount.amount < ZERO:
            raise InvalidIncomeError("Local Service Tax cannot be negative")
        self.monthly_amount = monthly_amount

    def calculate(self, ctx: TaxContext) -> TaxResult:
        return TaxResult(self.monthly_amount)


class VAT(Tax):
    """Compute output VAT, recoverable input VAT, and net VAT payable."""

    rate = Decimal("0.18")

    def calculate(self, ctx: TaxContext) -> TaxResult:
        output = ZERO_MONEY
        input_vat = ZERO_MONEY
        for invoice in ctx.invoices:
            if invoice.amount.amount < ZERO:
                raise InvalidIncomeError("Invoice amount cannot be negative")
            if invoice.supply is not SupplyType.STANDARD:
                continue
            vat = invoice.amount * self.rate
            if invoice.is_purchase:
                input_vat += vat
            else:
                output += vat
        return TaxResult(output + Money(-input_vat.amount), {"output_vat": output, "input_vat": input_vat})


class CorporateIncomeTax(Tax):
    """Resident-company tax on revenue less allowable deductions."""

    rate = Decimal("0.30")

    def calculate(self, ctx: TaxContext) -> TaxResult:
        chargeable = ctx.amount.amount - ctx.deductions.amount
        if chargeable < ZERO:
            raise InvalidIncomeError("Allowable deductions cannot exceed revenue")
        return TaxResult(Money(chargeable) * self.rate, {"chargeable_income": Money(chargeable)})


@dataclass(frozen=True)
class PayrollResult:
    """Payroll deductions and take-home pay for one month."""

    gross: Money
    nssf_employee: Money
    nssf_employer: Money
    local_service_tax: Money
    paye: Money
    net_pay: Money


class Payroll:
    """Apply employee NSSF and LST before calculating PAYE and net pay."""

    def __init__(self, lst: LocalServiceTax | None = None) -> None:
        self.nssf = NSSF()
        self.lst = lst or LocalServiceTax()
        self.paye = PAYE()

    def calculate(self, ctx: TaxContext) -> PayrollResult:
        gross = ctx.amount + ctx.allowances
        nssf = self.nssf.calculate(TaxContext(amount=ctx.amount))
        lst = self.lst.calculate(ctx).amount
        taxable_ctx = TaxContext(
            amount=ctx.amount,
            allowances=ctx.allowances,
            deductions=ctx.deductions + lst,
            resident=ctx.resident,
            effective_date=ctx.effective_date,
        )
        paye = self.paye.calculate(taxable_ctx).amount
        net = gross + Money(-nssf.amount.amount) + Money(-lst.amount) + Money(-paye.amount)
        return PayrollResult(gross, nssf.amount, nssf.breakdown["employer"], lst, paye, net)


@dataclass(frozen=True)
class TaxScenario:
    """A named scenario's income and already-calculated tax."""

    name: str
    income: Money
    tax: Money

    @property
    def take_home(self) -> Money:
        return Money(self.income.amount - self.tax.amount)


@dataclass(frozen=True)
class TaxPlanComparison:
    """Take-home comparison; positive difference favors the first scenario."""

    first: TaxScenario
    second: TaxScenario
    difference: Money


class TaxPlanner:
    """Compare two scenarios without assuming which tax applies to each."""

    def compare(self, first: TaxScenario, second: TaxScenario) -> TaxPlanComparison:
        return TaxPlanComparison(first, second, Money(first.take_home.amount - second.take_home.amount))
