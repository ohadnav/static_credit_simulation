from copy import deepcopy
from dataclasses import dataclass
from typing import Callable, List, Optional, Union, Tuple

from joblib import delayed

from common.constants import LoanSimulationType
from common.context import DataGenerator, SimulationContext
from common.numbers import Float
from common.util import TqdmParallel, LIVE_RATE
from finance.lender import Lender
from finance.loan_simulation import LoanSimulation
from seller.merchant import Merchant


@dataclass(unsafe_hash=True)
class MerchantCondition:
    field_name: Optional[str] = None
    loan_type: Optional[LoanSimulationType] = None
    min_value: Optional[Float] = None
    max_value: Optional[Float] = None


ConditionsEntityOrList = Union[MerchantCondition, List[MerchantCondition]]
ResultsType = Union[LoanSimulation, Float]
EntityOrList = Optional[Union[ResultsType, List[ResultsType]]]
ValidatorMethod = Callable[[Merchant], EntityOrList]
MerchantAndResult = Tuple[Merchant, EntityOrList]


class MerchantFactory:
    def __init__(self, data_generator: DataGenerator, context: SimulationContext):
        self.data_generator = data_generator
        self.context = context

    def generate_merchant_validator(self, conditions: ConditionsEntityOrList) -> ValidatorMethod:
        if isinstance(conditions, MerchantCondition):
            conditions = [conditions]

        def validator(merchant: Merchant) -> EntityOrList:
            values: List[Float] = [getattr(merchant, condition.field_name)(self.data_generator.start_date) for condition
                in
                conditions]
            for i in range(len(conditions)):
                if conditions[i].min_value is not None and not values[i] > conditions[i].min_value:
                    return None
                if conditions[i].max_value is not None and not values[i] < conditions[i].max_value:
                    return None
            return values if len(values) > 1 else values[0]

        return validator

    def generate_diff_validator(self, conditions: ConditionsEntityOrList) -> ValidatorMethod:
        lsr_validator = self.generate_lsr_validator(conditions)

        def validator(merchant: Merchant) -> EntityOrList:
            loans = lsr_validator(merchant)
            if loans is None:
                return None
            lsr = [loan.simulation_results for loan in loans]
            if len(lsr) > len(set(lsr)):
                return None
            return loans

        return validator

    def generate_lsr_validator(self, conditions: ConditionsEntityOrList) -> ValidatorMethod:
        if isinstance(conditions, MerchantCondition):
            conditions = [conditions]

        def validator(merchant: Merchant) -> EntityOrList:
            loans: List[LoanSimulation] = [
                Lender.loan_from_merchant(deepcopy(merchant), self.context, self.data_generator, c.loan_type) for c in
                conditions]
            for i in range(len(loans)):
                loans[i].simulate()
                if conditions[i].field_name:
                    value = getattr(loans[i].simulation_results, conditions[i].field_name)
                    if conditions[i].min_value is not None and not value > conditions[i].min_value:
                        return None
                    if conditions[i].max_value is not None and not value < conditions[i].max_value:
                        return None
            return loans if len(loans) > 1 else loans[0]

        return validator

    def generate_merchants(
            self, validator: Optional[ValidatorMethod] = None, num_merchants: Optional[int] = None,
            show_live_rate: bool = False) -> List[Union[MerchantAndResult, Merchant]]:
        num_merchants = num_merchants or self.data_generator.num_merchants
        if validator is None:
            return [Merchant.generate_simulated(self.data_generator) for _ in range(num_merchants)]
        if num_merchants > 1:
            if show_live_rate:
                LIVE_RATE.name = 'merchant_qualify'
                LIVE_RATE.reset()
            merchants_and_results = TqdmParallel(
                desc='Generating merchants', total=num_merchants, show_live_rate=show_live_rate)(
                delayed(self.merchant_generation_iteration)(validator, show_live_rate) for _ in range(num_merchants))
            return merchants_and_results
        else:
            return [self.merchant_generation_iteration(validator)]

    def merchant_generation_iteration(
            self, validator: ValidatorMethod, show_live_rate: bool = False) -> MerchantAndResult:
        while True:
            merchant = Merchant.generate_simulated(self.data_generator)
            if show_live_rate:
                LIVE_RATE.total += 1
            result = validator(merchant)
            if result:
                if show_live_rate:
                    LIVE_RATE.positive += 1
                return merchant, result
