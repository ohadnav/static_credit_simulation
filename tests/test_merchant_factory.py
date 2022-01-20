from copy import deepcopy
from unittest.mock import MagicMock

from common.enum import LoanSimulationType, LoanReferenceType
from common.numbers import Percent, Dollar, O, ONE, O_INT
from finance.lender import Lender
from finance.loan_simulation import LoanSimulation, LoanSimulationResults
from seller.merchant import Merchant
from simulation.merchant_factory import Condition, MerchantFactory
from statistical_tests.statistical_util import StatisticalTestCase


class TestMerchantFactory(StatisticalTestCase):
    def setUp(self) -> None:
        super(TestMerchantFactory, self).setUp()
        self.data_generator.num_merchants = 10
        self.merchant = Merchant.generate_simulated(self.data_generator)

    def generate_mock_loan(self):
        loan = LoanSimulation(self.context, self.data_generator, self.merchant)
        loan.simulate = MagicMock()
        loan.simulation_results = LoanSimulationResults(O, O, O, O, O, O, O, O, O, O, O, O, O_INT)
        return loan

    def generate_merchant_with_id(self, _id: int) -> Merchant:
        merchant = deepcopy(self.merchant)
        merchant.id = str(_id)
        merchant.int_id = _id
        return merchant

    def test_generate_merchant_validator(self):
        margin = Percent(0.1)
        self.merchant.profit_margin = MagicMock(return_value=margin)
        field_name = 'profit_margin'
        condition_gt = Condition(field_name, min_value=margin + 0.1)
        condition_eq = Condition(field_name, min_value=margin)
        condition_lt = Condition(field_name, min_value=margin - 0.1)
        self.assertIsNone(self.factory.generate_merchant_validator(condition_gt)(self.merchant))
        self.assertIsNone(self.factory.generate_merchant_validator(condition_eq)(self.merchant))
        self.assertEqual(self.factory.generate_merchant_validator(condition_lt)(self.merchant), margin)

    def test_generate_diff_validator(self):
        field_name = 'bankruptcy_rate'
        loan1 = self.generate_mock_loan()
        setattr(loan1.simulation_results, field_name, Percent(0.1))
        loan2 = self.generate_mock_loan()
        setattr(loan2.simulation_results, field_name, Percent(0.2))
        Lender.generate_loan = MagicMock(side_effect=[loan1, loan2, loan2, loan2])
        conditions = [Condition(field_name, LoanSimulationType.DEFAULT, O),
            Condition(field_name, LoanSimulationType.DEFAULT, O)]
        self.assertDeepAlmostEqual(
            self.factory.generate_diff_validator(conditions)(self.merchant), [loan1, loan2])
        self.assertIsNone(self.factory.generate_diff_validator(conditions)(self.merchant))

    def test_generate_with_reference_loan(self):
        self.data_generator.num_merchants = 1
        for loan_reference_type in LoanReferenceType.list():
            self.context.loan_reference_type = loan_reference_type
            condition1 = Condition(loan_type=LoanSimulationType.DEFAULT)
            condition2 = Condition(loan_type=LoanSimulationType.LINE_OF_CREDIT)
            merchant_and_results = self.factory.generate_from_conditions([condition1, condition2])
            loan1: LoanSimulation = merchant_and_results[0][1][0]
            loan2: LoanSimulation = merchant_and_results[0][1][1]
            self.assertIsNone(loan1.reference_loan)
            self.assertEqual(loan2.reference_loan, loan1)
            self.assertTrue(loan1.compare_reference_loan())

    def test_generate_lsr_validator(self):
        field_name = 'lender_profit'
        field_name2 = 'total_credit'
        profit = ONE
        credit = Dollar(10)
        loan1 = self.generate_mock_loan()
        setattr(loan1.simulation_results, field_name, profit)
        loan2 = self.generate_mock_loan()
        setattr(loan2.simulation_results, field_name2, credit)

        condition_gt = Condition(field_name, LoanSimulationType.DEFAULT, min_value=profit + 0.1)
        condition_eq = Condition(field_name, LoanSimulationType.DEFAULT, min_value=profit)
        condition_lt = Condition(field_name, LoanSimulationType.DEFAULT, min_value=profit - 0.1)
        condition2_lt = Condition(
            field_name2, LoanSimulationType.LINE_OF_CREDIT, min_value=credit - 0.1)
        condition2_gt = Condition(
            field_name2, LoanSimulationType.LINE_OF_CREDIT, min_value=credit + 0.1)

        Lender.generate_loan = MagicMock(return_value=loan1)
        self.assertIsNone(self.factory.generate_lsr_validator(condition_gt)(self.merchant))
        self.assertIsNone(self.factory.generate_lsr_validator(condition_eq)(self.merchant))
        self.assertDeepAlmostEqual(self.factory.generate_lsr_validator(condition_lt)(self.merchant), loan1)

        Lender.generate_loan = MagicMock(side_effect=[loan1, loan2, loan1, loan2, loan1, loan2])
        self.assertIsNone(
            self.factory.generate_lsr_validator([condition_gt, condition2_lt])(self.merchant))
        self.assertIsNone(
            self.factory.generate_lsr_validator([condition_lt, condition2_gt])(self.merchant))
        self.assertDeepAlmostEqual(
            self.factory.generate_lsr_validator([condition_lt, condition2_lt])(self.merchant),
            [loan1, loan2])

    def test_generate_merchants(self):
        merchants_and_results = self.factory.generate_merchants(
            self.factory.generate_merchant_validator(Condition('annual_top_line', min_value=Dollar(10 ** 5))))
        self.assertEqual(len(merchants_and_results), self.data_generator.num_merchants)
        self.assertEqual(
            len(set(MerchantFactory.get_merchants_from_results(merchants_and_results))),
            self.data_generator.num_merchants)
        merchants_and_results = self.factory.generate_merchants()
        self.assertEqual(type(merchants_and_results[0]), Merchant)
        self.assertEqual(len(merchants_and_results), self.data_generator.num_merchants)
        num_merchants = 4
        merchants_and_results = self.factory.generate_merchants(num_merchants=num_merchants)
        self.assertEqual(len(merchants_and_results), num_merchants)
