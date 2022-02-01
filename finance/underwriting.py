from common.context import SimulationContext, RiskConfiguration, DataGenerator, RiskContext
from common.local_numbers import Float, Percent, Ratio, Date, O, ONE
from common.util import weighted_average, min_max
from finance.risk_entity import RiskEntity


class Underwriting:
    def __init__(self, context: SimulationContext, data_generator: DataGenerator, entity: RiskEntity):
        self.context = context
        self.data_generator = data_generator
        self.initial_risk_context = self.calculate_score(entity, self.data_generator.start_date)

    @staticmethod
    def benchmark_variable_name(predictor: str) -> str:
        return f'{predictor}_benchmark'

    @staticmethod
    def risk_entity_method_name(predictor: str) -> str:
        return f'get_{predictor}'

    def calculate_score(self, entity: RiskEntity, day: Date) -> RiskContext:
        risk_context = RiskContext()
        for predictor in vars(self.context.risk_context).keys():
            risk_configuration = getattr(risk_context, predictor)
            risk_configuration.score = self.benchmark_score(entity, predictor, day)
        return risk_context

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

    def benchmark_score(self, entity: RiskEntity, predictor: str, day: Date):
        configuration: RiskConfiguration = getattr(self.context.risk_context, predictor)
        benchmark = getattr(self.context, Underwriting.benchmark_variable_name(predictor))
        value = getattr(entity, Underwriting.risk_entity_method_name(predictor))(day)
        score = self.benchmark_comparison(benchmark, value, configuration.higher_is_better, configuration.sensitivity)
        return score

    @staticmethod
    def aggregated_score(risk_context: RiskContext) -> Percent:
        scores = [configuration.score for configuration in vars(risk_context).values()]
        weights = [configuration.weight for configuration in vars(risk_context).values()]
        return weighted_average(scores, weights)

    def approved(self, entity: RiskEntity, day: Date) -> bool:
        risk_context = self.calculate_score(entity, day)
        for _, configuration in vars(risk_context).items():
            if configuration.score < configuration.threshold:
                return False
        if self.aggregated_score(risk_context) < self.context.min_risk_score:
            return False
        return True
