from unittest.mock import MagicMock

from common.constants import LoanSimulationType
from common.numbers import Percent, Dollar, O, ONE
from finance.lender import Lender
from finance.loan_simulation import LoanSimulation, LoanSimulationResults
from seller.merchant import Merchant
from simulation.merchant_factory import MerchantCondition
from tests.util_test import StatisticalTestCase


class TestMerchantFactory(StatisticalTestCase):
    def setUp(self) -> None:
        super(TestMerchantFactory, self).setUp()
        self.merchant = Merchant.generate_simulated(self.data_generator)

    def get_mock_loan(self):
        loan = LoanSimulation(self.context, self.data_generator, self.merchant)
        loan.simulate = MagicMock()
        loan.simulation_results = LoanSimulationResults(O, O, O, O, O, O, O, O, O, O)
        return loan

    def test_generate_merchant_validator(self):
        margin = Percent(0.1)
        self.merchant.profit_margin = MagicMock(return_value=margin)
        field_name = 'profit_margin'
        merchant_condition_gt = MerchantCondition(field_name, min_value=margin + 0.1)
        merchant_condition_eq = MerchantCondition(field_name, min_value=margin)
        merchant_condition_lt = MerchantCondition(field_name, min_value=margin - 0.1)
        self.assertIsNone(self.factory.generate_merchant_validator(merchant_condition_gt)(self.merchant))
        self.assertIsNone(self.factory.generate_merchant_validator(merchant_condition_eq)(self.merchant))
        self.assertEqual(self.factory.generate_merchant_validator(merchant_condition_lt)(self.merchant), margin)

    def test_generate_diff_validator(self):
        field_name = 'bankruptcy_rate'
        loan1 = self.get_mock_loan()
        setattr(loan1.simulation_results, field_name, Percent(0.1))
        loan2 = self.get_mock_loan()
        setattr(loan2.simulation_results, field_name, Percent(0.2))
        Lender.loan_from_merchant = MagicMock(side_effect=[loan1, loan2, loan2, loan2])
        merchant_conditions = [MerchantCondition(field_name, LoanSimulationType.DEFAULT, O),
            MerchantCondition(field_name, LoanSimulationType.DEFAULT, O)]
        self.assertDeepAlmostEqual(
            self.factory.generate_diff_validator(merchant_conditions)(self.merchant), [loan1, loan2])
        self.assertIsNone(self.factory.generate_diff_validator(merchant_conditions)(self.merchant))

    def test_generate_lsr_validator(self):
        field_name = 'lender_profit'
        field_name2 = 'total_credit'
        profit = ONE
        credit = Dollar(10)
        loan1 = self.get_mock_loan()
        setattr(loan1.simulation_results, field_name, profit)
        loan2 = self.get_mock_loan()
        setattr(loan2.simulation_results, field_name2, credit)

        merchant_condition_gt = MerchantCondition(field_name, LoanSimulationType.DEFAULT, min_value=profit + 0.1)
        merchant_condition_eq = MerchantCondition(field_name, LoanSimulationType.DEFAULT, min_value=profit)
        merchant_condition_lt = MerchantCondition(field_name, LoanSimulationType.DEFAULT, min_value=profit - 0.1)
        merchant_condition2_lt = MerchantCondition(
            field_name2, LoanSimulationType.LINE_OF_CREDIT, min_value=credit - 0.1)
        merchant_condition2_gt = MerchantCondition(
            field_name2, LoanSimulationType.LINE_OF_CREDIT, min_value=credit + 0.1)

        Lender.loan_from_merchant = MagicMock(return_value=loan1)
        self.assertIsNone(self.factory.generate_lsr_validator(merchant_condition_gt)(self.merchant))
        self.assertIsNone(self.factory.generate_lsr_validator(merchant_condition_eq)(self.merchant))
        self.assertDeepAlmostEqual(self.factory.generate_lsr_validator(merchant_condition_lt)(self.merchant), loan1)

        Lender.loan_from_merchant = MagicMock(side_effect=[loan1, loan2, loan1, loan2, loan1, loan2])
        self.assertIsNone(
            self.factory.generate_lsr_validator([merchant_condition_gt, merchant_condition2_lt])(self.merchant))
        self.assertIsNone(
            self.factory.generate_lsr_validator([merchant_condition_lt, merchant_condition2_gt])(self.merchant))
        self.assertDeepAlmostEqual(
            self.factory.generate_lsr_validator([merchant_condition_lt, merchant_condition2_lt])(self.merchant),
            [loan1, loan2])
