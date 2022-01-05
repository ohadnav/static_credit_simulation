import logging
import sys
from random import random
from unittest import TestCase
from unittest.mock import MagicMock

from autologging import TRACE

from common import constants
from common.context import DataGenerator, SimulationContext
from common.util import weighted_average
from finance.underwriting import Underwriting
from seller.merchant import Merchant


class TestUnderwriting(TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        logging.basicConfig(
            format=('%(filename)s: '
                    '%(levelname)s: '
                    '%(funcName)s(): '
                    '%(lineno)d:\t'
                    '%(message)s'),
            level=TRACE, stream=sys.stderr)

    def setUp(self) -> None:
        logging.info(f'****  setUp for {self._testMethodName} of {type(self).__name__}')
        self.data_generator = DataGenerator()
        self.context = SimulationContext()
        self.merchant = Merchant.generate_simulated(self.data_generator)
        self.underwriting = Underwriting(self.context, self.merchant)

    def test_init(self):
        for _, configuration in vars(self.underwriting.risk_context).items():
            self.assertIsNotNone(configuration.score)

    def test_update_score(self):
        scores = [random() for _ in range(len(list(vars(self.underwriting.risk_context))))]
        self.underwriting.benchmark_score = MagicMock(side_effect=scores)
        self.underwriting.update_score(constants.START_DATE)
        self.assertListEqual([c.score for c in vars(self.underwriting.risk_context).values()], scores)

    def test_benchmark_comparison(self):
        self.assertAlmostEqual(self.underwriting.benchmark_comparison(1, self.context.benchmark_factor, True), 1)
        self.assertAlmostEqual(self.underwriting.benchmark_comparison(1, 1 + self.context.benchmark_factor, True), 1)
        self.assertAlmostEqual(self.underwriting.benchmark_comparison(1, 1 / self.context.benchmark_factor, False), 1)
        self.assertAlmostEqual(
            self.underwriting.benchmark_comparison(1, 1 / self.context.benchmark_factor - 0.1, False), 1)
        self.assertAlmostEqual(self.underwriting.benchmark_comparison(1, 1, True), 1 / self.context.benchmark_factor)
        self.assertAlmostEqual(self.underwriting.benchmark_comparison(1, 1, False), 1 / self.context.benchmark_factor)
        self.assertAlmostEqual(
            self.underwriting.benchmark_comparison(2, 1, True), 1 / (2 * self.context.benchmark_factor))
        self.assertAlmostEqual(
            self.underwriting.benchmark_comparison(1, 2, False), 1 / (2 * self.context.benchmark_factor))

    def test_benchmark_score(self):
        for predictor, configuration in vars(self.context.risk_context).items():
            benchmark = getattr(self.context, f'{predictor}_benchmark')
            setattr(self.underwriting.merchant, predictor, MagicMock(return_value=benchmark))
            self.assertAlmostEqual(
                self.underwriting.benchmark_score(predictor, constants.START_DATE), 1 / self.context.benchmark_factor)

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
        self.assertTrue(self.underwriting.approved())
        for configuration in vars(self.underwriting.risk_context).values():
            configuration.score = configuration.threshold - 0.01
            self.assertFalse(self.underwriting.approved())
            configuration.score = 1
        self.underwriting.aggregated_score = MagicMock(return_value=self.context.min_risk_score - 0.01)
        self.assertFalse(self.underwriting.approved())
