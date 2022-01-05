from copy import deepcopy

from autologging import logged, traced

from common import constants
from common.context import SimulationContext, RiskConfiguration
from common.util import Percent, Date, weighted_average, min_max
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
        for predictor, risk_configuration in vars(self.risk_context).items():
            risk_configuration.score = self.benchmark_score(predictor, day)

    def benchmark_comparison(self, benchmark: float, value: float, higher_is_better: bool) -> Percent:
        if higher_is_better:
            assert benchmark > 0
            ratio = value / (benchmark * self.context.benchmark_factor)
        else:
            if value == 0:
                ratio = 1
            else:
                ratio = benchmark / (self.context.benchmark_factor * value)
        return min_max(ratio, 0, 1)

    def benchmark_score(self, predictor: str, day: Date):
        configuration: RiskConfiguration = getattr(self.context.risk_context, predictor)
        benchmark = getattr(self.context, f'{predictor}_benchmark')
        value = getattr(self.merchant, predictor)(day)
        return self.benchmark_comparison(benchmark, value, configuration.higher_is_better)

    def aggregated_score(self) -> Percent:
        scores = [configuration.score for configuration in vars(self.risk_context).values()]
        weights = [configuration.weight for configuration in vars(self.risk_context).values()]
        return weighted_average(scores, weights)

    def approved(self) -> bool:
        for _, configuration in vars(self.risk_context).items():
            if configuration.score < configuration.threshold:
                return False
        if self.aggregated_score() < self.context.min_risk_score:
            return False
        return True