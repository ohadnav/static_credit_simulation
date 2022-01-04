from copy import deepcopy
from dataclasses import dataclass, fields

from autologging import logged, traced

from common import constants
from common.context import SimulationContext, RiskConfiguration
from common.util import Percent, Date, Duration, weighted_average
from seller.merchant import Merchant


@traced
@logged
class Underwriting:
    def __init__(self, context: SimulationContext, merchant: Merchant):
        self.context = context
        self.merchant = merchant
        self.risk_context = deepcopy(self.context.risk_context)
        self.update_score(constants.START_DATE)

    def update_score(self, day: Date):
        for predictor, risk_configuration in self.risk_context.to_dict().items():
            risk_configuration.score = self.benchmark_score(predictor, day)

    def benchmark_comparison(self, benchmark: float, value: float, higher_is_better: bool) -> Percent:
        ratio = (self.context.benchmark_factor * value)/ benchmark
        if higher_is_better:
            if ratio == 0:
                return 0
            else:
                ratio = 1 / ratio
        return max(0.0, min(1.0, ratio))

    def benchmark_score(self, predictor: str, day: Date):
        configuration: RiskConfiguration = getattr(self.context.risk_context, predictor)
        benchmark = getattr(self.context, f'{predictor}_benchmark')
        self.merchant.debt_to_inventory(day)
        value = getattr(self.merchant, predictor)(day)
        return self.benchmark_comparison(benchmark, value, configuration.higher_is_better)

    def aggregated_score(self) -> Percent:
        scores = [configuration.score for configuration in self.risk_context.to_dict().values()]
        weights = [configuration.weight for configuration in self.risk_context.to_dict().values()]
        return weighted_average(scores, weights)

    def approved(self) -> bool:
        for _, configuration in self.risk_context.to_dict().items():
            if configuration.score < configuration.threshold:
                return False
        if self.aggregated_score() < self.context.min_risk_score:
            return False
        return True