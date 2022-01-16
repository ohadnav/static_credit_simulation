from copy import deepcopy
from random import random
from unittest.mock import MagicMock

from common import constants
from common.context import DataGenerator, SimulationContext
from common.util import weighted_average, ONE, TWO
from finance.underwriting import Underwriting
from seller.merchant import Merchant
from statistical_tests.statistical_test import statistical_test_bool
from tests.util_test import StatisticalTestCase


class TestUnderwriting(StatisticalTestCase):
    def setUp(self) -> None:
        super(TestUnderwriting, self).setUp()
        self.data_generator.max_num_products = 4
        self.data_generator.num_products = 2
        self.merchant = Merchant.generate_simulated(self.data_generator)
        self.underwriting = Underwriting(self.context, self.merchant)

    def test_init(self):
        for _, configuration in vars(self.underwriting.risk_context).items():
            self.assertIsNotNone(configuration.score)

    def test_update_score(self):
        scores = [random() for _ in range(len(list(vars(self.underwriting.risk_context))))]
        self.underwriting.benchmark_score = MagicMock(side_effect=scores)
        self.underwriting.update_score(constants.START_DATE)
        self.assertDeepAlmostEqual([c.score for c in vars(self.underwriting.risk_context).values()], scores)

    def test_benchmark_comparison(self):
        self.assertAlmostEqual(self.underwriting.benchmark_comparison(ONE, ONE, True, ONE), ONE)
        self.assertAlmostEqual(self.underwriting.benchmark_comparison(ONE, ONE + 0.1, True, ONE), ONE)

        self.assertAlmostEqual(self.underwriting.benchmark_comparison(ONE, ONE, False, ONE), ONE)
        self.assertAlmostEqual(self.underwriting.benchmark_comparison(ONE, ONE - 0.1, False, ONE), ONE)

        self.assertAlmostEqual(self.underwriting.benchmark_comparison(TWO, ONE, True, ONE), ONE / 2)
        self.assertAlmostEqual(self.underwriting.benchmark_comparison(ONE, TWO, False, ONE), ONE / 2)

        self.assertAlmostEqual(self.underwriting.benchmark_comparison(ONE, ONE, True, TWO), ONE)
        self.assertAlmostEqual(self.underwriting.benchmark_comparison(ONE, ONE, False, TWO), ONE)

        self.assertAlmostEqual(self.underwriting.benchmark_comparison(TWO, ONE, True, TWO), ONE / 2)
        self.assertAlmostEqual(self.underwriting.benchmark_comparison(ONE, TWO, False, TWO), ONE / 2)

        self.assertAlmostEqual(self.underwriting.benchmark_comparison(ONE * 3, ONE, True, TWO), ONE / 6)
        self.assertAlmostEqual(self.underwriting.benchmark_comparison(ONE, ONE * 3, False, TWO), ONE / 6)

    def test_benchmark_score(self):
        for predictor, configuration in vars(self.context.risk_context).items():
            benchmark = getattr(self.context, f'{predictor}_benchmark')
            setattr(self.underwriting.merchant, predictor, MagicMock(return_value=benchmark))
            self.assertAlmostEqual(self.underwriting.benchmark_score(predictor, constants.START_DATE), ONE)
            if hasattr(self.data_generator, f'{predictor}_median'):
                median = getattr(self.data_generator, f'{predictor}_median')
                setattr(self.underwriting.merchant, predictor, MagicMock(return_value=median))
                self.assertLess(self.underwriting.benchmark_score(predictor, constants.START_DATE), ONE)

    def test_aggregated_score(self):
        scores = [random() for _ in range(len(list(vars(self.underwriting.risk_context))))]
        weights = [random() for _ in range(len(list(vars(self.underwriting.risk_context))))]
        for i, k in enumerate(vars(self.underwriting.risk_context)):
            vars(self.underwriting.risk_context)[k].score = scores[i]
            vars(self.underwriting.risk_context)[k].weight = weights[i]
        self.assertAlmostEqual(self.underwriting.aggregated_score(), weighted_average(scores, weights))

    def test_approved(self):
        for configuration in vars(self.underwriting.risk_context).values():
            configuration.score = 1
        self.assertTrue(self.underwriting.approved(constants.START_DATE))
        for configuration in vars(self.underwriting.risk_context).values():
            configuration.score = configuration.threshold - 0.01
            self.assertFalse(self.underwriting.approved(constants.START_DATE))
            configuration.score = 1
        self.underwriting.aggregated_score = MagicMock(return_value=self.context.min_risk_score - 0.01)
        self.assertFalse(self.underwriting.approved(constants.START_DATE))

    def test_risk_factors(self):
        for predictor, configuration in vars(self.context.risk_context).items():
            def test_factor(data_generator: DataGenerator, context: SimulationContext, *args, **kwargs):
                def return_benchmark(*args, **kwargs):
                    return benchmark

                def return_benchmark_multiplied(*args, **kwargs):
                    return benchmark / 2 if configuration.higher_is_better else benchmark * 2

                is_true = []
                merchant1 = Merchant.generate_simulated(data_generator)
                merchant2 = deepcopy(merchant1)
                benchmark = getattr(context, f'{predictor}_benchmark')
                setattr(merchant1, predictor, return_benchmark)
                setattr(merchant2, predictor, return_benchmark_multiplied)
                underwriting1 = Underwriting(context, merchant1)
                underwriting2 = Underwriting(context, merchant2)
                is_true.append(
                    (underwriting1.aggregated_score() > underwriting2.aggregated_score(),
                    (predictor, merchant1, merchant2)))
                return is_true

            statistical_test_bool(self, test_factor, min_frequency=0.9, times=10)
