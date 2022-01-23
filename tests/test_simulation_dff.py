from copy import deepcopy
from random import randint
from unittest.mock import MagicMock, call

from common import constants
from common.enum import LoanSimulationType
from common.numbers import ONE, O, ONE_INT, Date, Duration
from finance.loan_simulation import LoanSimulation
from finance.simulation_dff import LoanSimulationDiff, LEDGER_ATTRIBUTES, MERCHANT_ATTRIBUTES
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
        self.lsd = LoanSimulationDiff(self.loan1, self.loan2)

    def test_no_diff(self):
        self.assertDeepAlmostEqual(self.lsd.get_diff(), {})

    def test_today_diff(self):
        self.loan2.today += 1
        self.assertDeepAlmostEqual(self.lsd.get_diff(), {'today': -1})

    def test_ledger_diff(self):
        self.lsd.ledger_attribute_diff = MagicMock()
        self.lsd.ledger_cash_history_diff = MagicMock()
        self.lsd.ledger_diff()
        self.lsd.ledger_attribute_diff.assert_has_calls([call(a) for a in LEDGER_ATTRIBUTES])
        self.lsd.ledger_cash_history_diff.assert_called_once()

    def test_merchant_diff(self):
        self.lsd.merchant_attribute_diff = MagicMock()
        self.lsd.merchant_stock_diff = MagicMock()
        self.lsd.merchant_diff()
        self.lsd.merchant_attribute_diff.assert_has_calls([call(a) for a in MERCHANT_ATTRIBUTES])
        self.lsd.merchant_stock_diff.assert_called_once()

    def test_ledger_cash_history_diff(self):
        self.lsd.diff['ledger'] = {}
        self.loan2.ledger.cash_history[self.data_generator.start_date] = O
        self.lsd.ledger_cash_history_diff()
        self.assertDeepAlmostEqual(
            self.lsd.diff, {'ledger': {'cash_history': {
                self.data_generator.start_date: self.loan1.ledger.cash_history[self.data_generator.start_date]}}})
        self.loan2.ledger.cash_history[self.data_generator.start_date] = self.loan1.ledger.cash_history[
            self.data_generator.start_date]
        self.loan1.ledger.cash_history.pop(self.data_generator.start_date + 1, None)
        self.loan2.ledger.cash_history[self.data_generator.start_date + 1] = ONE
        self.lsd.ledger_cash_history_diff()
        self.assertDeepAlmostEqual(
            self.lsd.diff, {'ledger': {'cash_history': {
                self.data_generator.start_date + 1: self.loan1.ledger.cash_history[
                                                        self.data_generator.start_date] - ONE}}})

    def test_ledger_attribute_diff(self):
        for attribute in LEDGER_ATTRIBUTES:
            self.lsd.diff['ledger'] = {}
            ledger_list1 = getattr(self.loan1.ledger, attribute)
            ledger_list2 = getattr(self.loan2.ledger, attribute)
            if ledger_list1:
                ledger_list2[0].amount -= ONE
                self.lsd.ledger_attribute_diff(attribute)
                self.assertDeepAlmostEqual(self.lsd.diff, {'ledger': {attribute: [(ledger_list1[0], ledger_list2[0])]}})
                ledger_list2[0].amount += ONE
                self.lsd.ledger_attribute_diff(attribute)
                self.assertDeepAlmostEqual(self.lsd.diff, {'ledger': {}})
                ledger_list2.pop()
                self.lsd.ledger_attribute_diff(attribute)
                self.assertDeepAlmostEqual(self.lsd.diff, {'ledger': {attribute: [(ledger_list1[-1], None)]}})
            else:
                self.lsd.ledger_attribute_diff(attribute)
                self.assertDeepAlmostEqual(self.lsd.diff, {'ledger': {}})

    def test_merchant_stock_diff(self):
        self.lsd.diff['merchant'] = {}
        i = randint(0, len(self.loan2.merchant.inventories) - 1)
        j = randint(0, len(self.loan2.merchant.inventories[0].batches) - 1)
        self.loan2.merchant.inventories[i].batches[j].stock -= ONE_INT
        self.lsd.merchant_stock_diff()
        self.assertDeepAlmostEqual(self.lsd.diff, {'merchant': {'stock': {i: (j, 1)}}})

    def test_merchant_attribute_diff(self):
        for attribute in MERCHANT_ATTRIBUTES:
            self.lsd.diff['merchant'] = {}
            attribute_func = getattr(self.loan2.merchant, attribute)
            expected_values = [attribute_func(Date(day)) for day in
                range(self.data_generator.start_date, self.loan1.today + 1)]
            expected_values[-1] -= ONE
            setattr(self.loan2.merchant, attribute, MagicMock(side_effect=expected_values))
            self.lsd.merchant_attribute_diff(attribute)
            self.assertDeepAlmostEqual(
                self.lsd.diff, {'merchant': {attribute: {self.loan1.today: ONE}}})
            setattr(self.loan2.merchant, attribute, attribute_func)
            self.lsd.merchant_attribute_diff(attribute)
            self.assertDeepAlmostEqual(self.lsd.diff, {'merchant': {}})
