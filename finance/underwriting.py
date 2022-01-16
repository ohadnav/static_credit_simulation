from copy import deepcopy

from common import constants
from common.context import SimulationContext, RiskConfiguration
from common.util import Percent, Date, weighted_average, min_max, Ratio, Float, ONE, O
from seller.merchant import Merchant


class Underwriting:
    def __init__(self, context: SimulationContext, merchant: Merchant):
        self.context = context
        self.merchant = merchant
        self.risk_context = deepcopy(self.context.risk_context)
        self.update_score(constants.START_DATE)
        self.initial_risk_context = deepcopy(self.risk_context)

    def update_score(self, day: Date):
        for predictor, risk_configuration in vars(self.risk_context).items():
            risk_configuration.score = self.benchmark_score(predictor, day)

    def benchmark_comparison(
            self, benchmark: Float, value: Float, higher_is_better: bool, sensitivity: Ratio) -> Percent:
        assert benchmark > O
        if higher_is_better:
            if value <= O:
                return O
            ratio = value / benchmark
        else:
            if value <= O:
                return ONE
            ratio = benchmark / value
        ratio = sensitivity * (ratio - 0.5) + 0.5
        return min_max(ratio, O, ONE)

    def benchmark_score(self, predictor: str, day: Date):
        configuration: RiskConfiguration = getattr(self.context.risk_context, predictor)
        benchmark = getattr(self.context, f'{predictor}_benchmark')
        value = getattr(self.merchant, predictor)(day)
        score = self.benchmark_comparison(benchmark, value, configuration.higher_is_better, configuration.sensitivity)
        return score

    def aggregated_score(self) -> Percent:
        scores = [configuration.score for configuration in vars(self.risk_context).values()]
        weights = [configuration.weight for configuration in vars(self.risk_context).values()]
        return weighted_average(scores, weights)

    def approved(self, day: Date) -> bool:
        for _, configuration in vars(self.risk_context).items():
            if configuration.score < configuration.threshold:
                return False
        if self.aggregated_score() < self.context.min_risk_score:
            return False
        if self.merchant.is_suspended(day):
            return False
        return True
