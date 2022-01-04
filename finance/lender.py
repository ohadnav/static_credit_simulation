from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import List, MutableMapping, Iterable, Optional

from autologging import logged, traced
from tqdm import tqdm

from common.context import SimulationContext, DataGenerator
from common.util import Percent, Dollar
from common.primitives import Primitive
from finance.loan import LoanSimulationResults, Loan, FlatFeeRBF
from seller.merchant import Merchant


@dataclass
class InvestmentRisk:
    sharpe: float
    r_squared: Percent
    beta: float
    value_at_risk: Percent


@dataclass
class LenderSimulationResults:
    lender_gross_profit: Dollar
    investment_risk: InvestmentRisk
    all_merchants: LoanSimulationResults
    portfolio_merchants: LoanSimulationResults


@traced
@logged
class Lender(Primitive):
    def __init__(self, context: SimulationContext, data_generator: DataGenerator, merchants: List[Merchant]):
        super(Lender, self).__init__(data_generator)
        self.merchants = merchants
        self.context = context
        self.simulation_results: Optional[LenderSimulationResults] = None
        self.loans: MutableMapping[Merchant, Loan] = {}

    def calculate_profit(self, loan: Loan) -> Dollar:
        pass

    def loan_from_merchant(self, merchant: Merchant) -> Loan:
        return Loan(self.context, self.data_generator, merchant)

    def aggregate_results(self, loan_results: Iterable[LoanSimulationResults]) -> LoanSimulationResults:
        pass

    def calculate_investment_risk(self) -> InvestmentRisk:
        pass

    def calculate_results(self):
        total_profit = sum([self.calculate_profit(loan) for loan in self.loans])
        investment_risk = self.calculate_investment_risk()
        all_merchants = self.aggregate_results([loan.simulation_results for loan in self.loans.values()])
        portfolio_merchants = self.aggregate_results([loan.simulation_results for loan in self.loans.values() if loan.approved])
        self.simulation_results = LenderSimulationResults(total_profit, investment_risk, all_merchants, portfolio_merchants)

    def simulate(self):
        for merchant in tqdm(self.merchants, desc=f'{type(self).__name__}: '):
            self.loans[merchant] = self.loan_from_merchant(merchant)
            self.loans[merchant].simulate()
        self.calculate_results()
