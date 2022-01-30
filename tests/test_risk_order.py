from common import constants
from common.numbers import Percent, O, TWO_INT, O_INT, Int, ONE, ONE_INT, FloatRange
from finance.risk_order import RiskOrder
from tests.util_test import BaseTestCase


class TestRiskOrder(BaseTestCase):
    def test_init_risk_orders(self):
        three = Int(3)
        cagrs = [self.data_generator.random() + ONE for _ in range(RiskOrder.default_num_mid_buckets() * three)]
        risk_order = RiskOrder(cagrs)
        self.assertEqual(len(risk_order.risk_orders), constants.NUM_RISK_ORDERS)
        self.assertDeepAlmostEqual(risk_order.count_per_order(cagrs), [O_INT, three, three, three, O_INT])

        cagrs2 = [Percent(x) for x in
            [-1, -0.5, 0, 0.1, 1.1, 1.2, 2.1, 2.2, constants.WHALE_GROWTH_CAGR, constants.WHALE_GROWTH_CAGR + 1]]
        risk_order2 = RiskOrder(cagrs2)
        self.assertDeepAlmostEqual(risk_order2.count_per_order(cagrs2), [TWO_INT, TWO_INT, TWO_INT, TWO_INT, TWO_INT])
        self.assertDeepAlmostEqual(
            risk_order2.risk_orders, [FloatRange(max_value=O), FloatRange(O, Percent(1.1)),
                FloatRange(Percent(1.1), Percent(2.1)), FloatRange(Percent(2.1), Percent(constants.WHALE_GROWTH_CAGR)),
                FloatRange(min_value=Percent(constants.WHALE_GROWTH_CAGR))])

    def test_get_order(self):
        cagrs = sorted([self.data_generator.random() + ONE for _ in range(RiskOrder.default_num_mid_buckets() * 3)])
        risk_order = RiskOrder(cagrs)
        self.assertEqual(risk_order.get_order(cagrs[0]), ONE_INT)
        self.assertEqual(risk_order.get_order(cagrs[-1]), Int(constants.NUM_RISK_ORDERS - 2))
        self.assertEqual(risk_order.get_order(constants.WHALE_GROWTH_CAGR), Int(constants.NUM_RISK_ORDERS - 1))
        self.assertEqual(risk_order.get_order(O - 0.1), O_INT)
