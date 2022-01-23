from copy import deepcopy
from random import randint
from unittest.mock import MagicMock, call

from common import constants
from common.enum import LoanSimulationType
from common.numbers import ONE, O, ONE_INT, Date, Duration
from finance.loan_simulation import LoanSimulation
from finance.simulation_dff import LoanSimulationDiff, MERCHANT_ATTRIBUTES
from seller.merchant import Merchant
from simulation.merchant_factory import Condition
from tests.util_test import BaseTestCase


class TestLoanSimulationDiff(BaseTestCase):
    def setUp(self) -> None:
        super(TestLoanSimulationDiff, self).setUp()
        self.data_generator.simulated_duration = Duration(constants.YEAR)
        self.data_generator.max_num_products = 2
        self.data_generator.num_merchants = 1
        result = self.factory.generate_from_conditions([Condition('total_credit', LoanSimulationType.DEFAULT, O)])[0]
        self.merchant: Merchant = result[0]
        self.loan1: LoanSimulation = result[1]
        self.loan2 = deepcopy(self.loan1)
        self.loan1.set_reference_loan(self.loan2)
        self.lsd = LoanSimulationDiff(
            self.data_generator, self.context, self.loan1.to_data_container(), self.loan2.to_data_container())

    def test_no_diff(self):
        self.assertDeepAlmostEqual(self.loan1.calculate_reference_diff(), {})

    def test_ledger_diff(self):
        self.lsd.ledger_loans_history_diff = MagicMock()
        self.lsd.ledger_repayments_diff = MagicMock()
        self.lsd.ledger_cash_history_diff = MagicMock()
        self.lsd.ledger_diff(self.loan1.today, self.loan2.today)
        self.lsd.ledger_cash_history_diff.assert_called_once()
        self.lsd.ledger_loans_history_diff.assert_called_once()
        self.lsd.ledger_repayments_diff.assert_called_once()

    def test_merchant_diff(self):
        self.lsd.merchant_attribute_diff = MagicMock()
        self.lsd.merchant_stock_diff = MagicMock()
        self.lsd.merchant_diff(self.loan1.today, self.loan2.today)
        self.lsd.merchant_attribute_diff.assert_has_calls(
            [call(a, self.loan1.today, self.loan2.today) for a in MERCHANT_ATTRIBUTES])
        self.lsd.merchant_stock_diff.assert_called_once()

    def test_ledger_cash_history_diff(self):
        self.lsd.diff['ledger'] = {}
        self.loan2.ledger.cash_history[self.data_generator.start_date] = O
        self.lsd.ledger_cash_history_diff(self.loan1.today, self.loan2.today)
        self.assertDeepAlmostEqual(
            self.lsd.diff, {'ledger': {'cash_history': {
                self.data_generator.start_date: self.loan1.ledger.cash_history[self.data_generator.start_date]}}})
        self.loan2.ledger.cash_history[self.data_generator.start_date] = self.loan1.ledger.cash_history[
            self.data_generator.start_date]
        self.loan1.ledger.cash_history.pop(self.data_generator.start_date + 1, None)
        self.loan2.ledger.cash_history[self.data_generator.start_date + 1] = ONE
        self.lsd.ledger_cash_history_diff(self.loan1.today, self.loan2.today)
        self.assertDeepAlmostEqual(
            self.lsd.diff, {'ledger': {'cash_history': {
                self.data_generator.start_date + 1: self.loan1.ledger.cash_history[
                                                        self.data_generator.start_date] - ONE}}})

    def test_ledger_repayments_diff(self):
        self.lsd.diff['ledger'] = {}
        self.loan2.ledger.repayments[0].amount -= ONE
        self.lsd.ledger_repayments_diff(self.loan1.today, self.loan2.today)
        self.assertDeepAlmostEqual(
            self.lsd.diff,
            {'ledger': {'repayments': {self.loan1.ledger.repayments[0].day: ONE}}})
        self.loan2.ledger.repayments[0].amount += ONE
        self.lsd.ledger_repayments_diff(self.loan1.today, self.loan2.today)
        self.assertDeepAlmostEqual(self.lsd.diff, {'ledger': {}})
        self.loan2.ledger.repayments.pop(0)
        self.lsd.ledger_repayments_diff(self.loan1.today, self.loan2.today)
        self.assertDeepAlmostEqual(
            self.lsd.diff,
            {'ledger': {'repayments': {self.loan1.ledger.repayments[0].day: self.loan1.ledger.repayments[0].amount}}})

    def test_ledger_loans_history_diff(self):
        self.lsd.diff['ledger'] = {}
        self.loan2.ledger.loans_history[0].amount -= ONE
        self.lsd.ledger_loans_history_diff()
        self.assertDeepAlmostEqual(
            self.lsd.diff,
            {'ledger': {'loans_history': [(self.loan1.ledger.loans_history[0], self.loan2.ledger.loans_history[0])]}})
        self.loan2.ledger.loans_history[0].amount += ONE
        self.lsd.ledger_loans_history_diff()
        self.assertDeepAlmostEqual(self.lsd.diff, {'ledger': {}})
        self.loan2.ledger.loans_history.pop()
        self.lsd.ledger_loans_history_diff()
        self.assertDeepAlmostEqual(
            self.lsd.diff, {'ledger': {'loans_history': [(self.loan1.ledger.loans_history[-1], None)]}})

    def test_merchant_stock_diff(self):
        self.lsd.diff['merchant'] = {}
        i = randint(0, len(self.loan2.merchant.inventories) - 1)
        j = randint(0, len(self.loan2.merchant.inventories[i].batches) - 1)
        self.loan2.merchant.inventories[i].batches[j].stock -= ONE_INT
        self.lsd.merchant_stock_diff(self.loan1.today, self.loan2.today)
        self.assertDeepAlmostEqual(
            self.lsd.diff,
            {'merchant': {'stock': {i: (j, 1, self.loan2.merchant.inventories[i].batches[j].start_date)}}})

    def test_merchant_attribute_diff(self):
        for attribute in MERCHANT_ATTRIBUTES:
            self.lsd.diff['merchant'] = {}
            attribute_func = getattr(self.loan2.merchant, attribute)
            expected_values = [attribute_func(Date(day)) for day in
                range(self.data_generator.start_date, self.loan1.today + 1)]
            expected_values[-1] -= ONE
            setattr(self.loan2.merchant, attribute, MagicMock(side_effect=expected_values))
            self.lsd.merchant_attribute_diff(attribute, self.loan1.today, self.loan2.today)
            self.assertDeepAlmostEqual(
                self.lsd.diff, {'merchant': {attribute: {self.loan1.today: ONE}}})
            setattr(self.loan2.merchant, attribute, attribute_func)
            self.lsd.merchant_attribute_diff(attribute, self.loan1.today, self.loan2.today)
            self.assertDeepAlmostEqual(self.lsd.diff, {'merchant': {}})

    def test_fast_diff(self):
        self.loan2.ledger.loans_history[-1].amount -= ONE
        self.assertTrue(self.lsd.fast_diff(self.loan1.today, self.loan2.today))
        self.assertFalse(self.lsd.fast_diff(self.loan1.today, self.loan2.ledger.loans_history[-1].start_date - 1))
