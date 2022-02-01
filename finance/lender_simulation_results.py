from __future__ import annotations

from loan_simulation_results import AggregatedLoanSimulationResults


class LenderSimulationResults:
    def __init__(
            self, all_merchants: AggregatedLoanSimulationResults, funded_merchants: AggregatedLoanSimulationResults):
        self.funded = funded_merchants
        self.all = all_merchants

    def __eq__(self, other):
        return self.all == other.all and self.funded == other.funded

    def __str__(self):
        return f'funded: {self.funded} all_lsr: {self.all}'

    def __repr__(self):
        return self.__str__()
