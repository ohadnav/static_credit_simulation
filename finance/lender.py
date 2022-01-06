from dataclasses import fields
from typing import List, MutableMapping, Iterable, Optional

import dacite as dacite
import numpy as np
from autologging import logged, traced

from common.context import SimulationContext, DataGenerator
from common.primitives import Primitive
from common.util import Dollar, weighted_average
from finance.loan import LoanSimulationResults, Loan
from seller.merchant import Merchant


class LenderSimulationResults:
    def __init__(self, lender_gross_profit: Dollar, sharpe: float,
                 all_merchants: LoanSimulationResults, portfolio_merchants: LoanSimulationResults):
        self.lender_gross_profit = lender_gross_profit
        self.sharpe = sharpe
        self.all_merchants = all_merchants
        self.portfolio_merchants = portfolio_merchants

    def __eq__(self, other):
        if not isinstance(other, LenderSimulationResults):
            return False
        return self.lender_gross_profit == other.lender_gross_profit \
               and self.sharpe == other.sharpe \
               and self.all_merchants == other.all_merchants \
               and self.portfolio_merchants == other.portfolio_merchants


@traced
@logged
class Lender(Primitive):
    def __init__(self, context: SimulationContext, data_generator: DataGenerator, merchants: List[Merchant]):
        super(Lender, self).__init__(data_generator)
        self.merchants = merchants
        self.context = context
        self.simulation_results: Optional[LenderSimulationResults] = None
        self.loans: MutableMapping[Merchant, Loan] = {}

    def loan_from_merchant(self, merchant: Merchant) -> Loan:
        return Loan(self.context, self.data_generator, merchant)

    @staticmethod
    def aggregate_results(loan_results: Iterable[LoanSimulationResults]) -> LoanSimulationResults:
        result = {}
        for field in fields(LoanSimulationResults):
            if field.name == 'valuation':
                result[field.name] = None
            elif field.name == 'lender_profit':
                result[field.name] = sum([lsr.lender_profit for lsr in loan_results])
            else:
                values = []
                weights = []
                for lsr in loan_results:
                    values.append(getattr(lsr, field.name))
                    weights.append(lsr.valuation)
                result[field.name] = weighted_average(values, weights)
        return dacite.from_dict(LoanSimulationResults, result)

    def calculate_sharpe(self, portfolio_results: Iterable[LoanSimulationResults]) -> float:
        aggregated = Lender.aggregate_results(portfolio_results)
        portfolio_return = aggregated.apr
        risk_free_return = self.context.cost_of_capital
        std = np.std([lsr.apr for lsr in portfolio_results])
        sharpe = (portfolio_return - risk_free_return) / std
        return sharpe

    def calculate_results(self):
        all_merchants = self.aggregate_results([loan.simulation_results for loan in self.loans.values()])
        portfolio_results = [loan.simulation_results for loan in self.loans.values() if loan.total_debt > 0]
        portfolio_merchants = self.aggregate_results(portfolio_results)
        sharpe = self.calculate_sharpe(portfolio_results)
        self.simulation_results = LenderSimulationResults(
            portfolio_merchants.lender_profit, sharpe, all_merchants, portfolio_merchants)

    def simulate(self):
        for merchant in self.merchants:
            self.loans[merchant] = self.loan_from_merchant(merchant)
            self.loans[merchant].simulate()
        self.calculate_results()
