from copy import deepcopy
from random import random
from unittest.mock import MagicMock

from common.context import DataGenerator, SimulationContext, RiskContext
from common.local_numbers import ONE, TWO, Float
from common.util import weighted_average
from finance.risk_entity import RiskEntity
from finance.underwriting import Underwriting
from seller.merchant import Merchant
from statistical_tests.statistical_util import statistical_test_bool, StatisticalTestCase


class TestUnderwriting(StatisticalTestCase):
    def setUp(self) -> None:
        super(TestUnderwriting, self).setUp()
        self.data_generator.max_num_products = 4
        self.data_generator.num_products = 2
        self.merchant = Merchant.generate_simulated(self.data_generator)
        self.underwriting = Underwriting(self.context, self.data_generator, self.merchant)

    def first_batch(self):
        return self.merchant.inventories[0].batches[0]

    def mock_entity_value(self, entity: RiskEntity, value: Float, predictor: str):
        setattr(entity, Underwriting.risk_entity_method_name(predictor), MagicMock(return_value=value))

    def test_init(self):
        for _, configuration in vars(self.underwriting.initial_risk_context).items():
            self.assertIsNotNone(configuration.score)

    def test_calculate_score(self):
        scores = [random() for _ in self.context.risk_context.to_dict().keys()]
        self.underwriting.benchmark_score = MagicMock(side_effect=scores)
        risk_context = self.underwriting.calculate_score(self.merchant, self.data_generator.start_date)
        self.assertDeepAlmostEqual([c.score for c in vars(risk_context).values()], scores)
        self.underwriting.benchmark_score = MagicMock(side_effect=scores)
        risk_context = self.underwriting.calculate_score(self.first_batch(), self.data_generator.start_date)
        self.assertDeepAlmostEqual([c.score for c in vars(risk_context).values()], scores)

    def test_benchmark_comparison(self):
        self.assertEqual(self.underwriting.benchmark_comparison(ONE, ONE, True, ONE), ONE)
        self.assertEqual(self.underwriting.benchmark_comparison(ONE, ONE + 0.1, True, ONE), ONE)

        self.assertEqual(self.underwriting.benchmark_comparison(ONE, ONE, False, ONE), ONE)
        self.assertEqual(self.underwriting.benchmark_comparison(ONE, ONE - 0.1, False, ONE), ONE)

        self.assertEqual(self.underwriting.benchmark_comparison(TWO, ONE, True, ONE), ONE / 2)
        self.assertEqual(self.underwriting.benchmark_comparison(ONE, TWO, False, ONE), ONE / 2)

        self.assertEqual(self.underwriting.benchmark_comparison(ONE, ONE, True, TWO), ONE)
        self.assertEqual(self.underwriting.benchmark_comparison(ONE, ONE, False, TWO), ONE)

        self.assertEqual(self.underwriting.benchmark_comparison(TWO, ONE, True, TWO), ONE / 2)
        self.assertEqual(self.underwriting.benchmark_comparison(ONE, TWO, False, TWO), ONE / 2)

        self.assertEqual(self.underwriting.benchmark_comparison(ONE * 3, ONE, True, TWO), ONE / 6)
        self.assertEqual(self.underwriting.benchmark_comparison(ONE, ONE * 3, False, TWO), ONE / 6)

    def test_benchmark_score(self):
        for predictor, configuration in vars(self.context.risk_context).items():
            benchmark = getattr(self.context, Underwriting.benchmark_variable_name(predictor))
            self.mock_entity_value(self.merchant, benchmark, predictor)
            self.mock_entity_value(self.first_batch(), benchmark, predictor)
            self.assertEqual(
                self.underwriting.benchmark_score(self.merchant, predictor, self.data_generator.start_date), ONE)
            if hasattr(self.data_generator, f'{predictor}_median'):
                median = getattr(self.data_generator, f'{predictor}_median')
                self.mock_entity_value(self.merchant, median, predictor)
                self.mock_entity_value(self.first_batch(), median, predictor)
                self.assertLess(
                    self.underwriting.benchmark_score(self.merchant, predictor, self.data_generator.start_date), ONE)
                self.assertLess(
                    self.underwriting.benchmark_score(self.first_batch(), predictor, self.data_generator.start_date),
                    ONE)

    def test_aggregated_score(self):
        scores = [random() for _ in range(len(list(vars(self.context.risk_context))))]
        weights = [random() for _ in range(len(list(vars(self.context.risk_context))))]
        risk_context = RiskContext()
        for i, k in enumerate(vars(risk_context)):
            vars(risk_context)[k].score = scores[i]
            vars(risk_context)[k].weight = weights[i]
        self.assertEqual(self.underwriting.aggregated_score(risk_context), weighted_average(scores, weights))

    def test_approved(self):
        risk_context = RiskContext()
        for predictor in vars(risk_context).keys():
            risk_configuration = getattr(risk_context, predictor)
            risk_configuration.score = ONE
        self.underwriting.calculate_score = MagicMock(return_value=risk_context)
        self.assertTrue(self.underwriting.approved(self.merchant, self.data_generator.start_date))
        self.assertTrue(self.underwriting.approved(self.first_batch(), self.data_generator.start_date))
        for configuration in vars(risk_context).values():
            configuration.score = configuration.threshold - 0.01
            self.assertFalse(self.underwriting.approved(self.merchant, self.data_generator.start_date))
            self.assertFalse(self.underwriting.approved(self.first_batch(), self.data_generator.start_date))
            configuration.score = 1
        self.underwriting.aggregated_score = MagicMock(return_value=self.context.min_risk_score - 0.01)
        self.assertFalse(self.underwriting.approved(self.merchant, self.data_generator.start_date))
        self.assertFalse(self.underwriting.approved(self.first_batch(), self.data_generator.start_date))

    def test_risk_factors(self):
        def test_factor(data_generator: DataGenerator, context: SimulationContext, *args, **kwargs):
            def return_benchmark(*args, **kwargs):
                return benchmark

            def return_benchmark_multiplied(*args, **kwargs):
                return benchmark / 2 if configuration.higher_is_better else benchmark * 2

            _predictor = kwargs['predictor']
            is_true = []
            merchant1 = Merchant.generate_simulated(data_generator)
            merchant2 = deepcopy(merchant1)
            benchmark = getattr(context, f'{_predictor}_benchmark')
            setattr(merchant1, Underwriting.risk_entity_method_name(_predictor), return_benchmark)
            setattr(merchant2, Underwriting.risk_entity_method_name(_predictor), return_benchmark_multiplied)
            underwriting1 = Underwriting(context, data_generator, merchant1)
            underwriting2 = Underwriting(context, data_generator, merchant2)
            is_true.append(
                (Underwriting.aggregated_score(underwriting1.initial_risk_context) > Underwriting.aggregated_score(
                    underwriting2.initial_risk_context),
                (_predictor, merchant1, merchant2)))
            return is_true

        for predictor, configuration in vars(self.context.risk_context).items():
            print(f'Testing..{predictor}')
            statistical_test_bool(self, test_factor, min_frequency=0.9, times=10, predictor=predictor)
