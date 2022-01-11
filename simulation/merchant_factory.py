from copy import deepcopy
from dataclasses import dataclass
from typing import Callable, List, Optional, Union, Tuple, Any

from joblib import delayed

from common import constants
from common.constants import LoanSimulationType
from common.context import DataGenerator, SimulationContext
from common.util import TqdmParallel
from finance.lender import Lender
from finance.loan_simulation import LoanSimulationResults, LoanSimulation
from seller.merchant import Merchant


@dataclass
class MerchantCondition:
    field_name: Optional[str] = None
    loan_type: LoanSimulationType = LoanSimulationType.DEFAULT
    min_value: Optional[float] = None
    max_value: Optional[float] = None


ResultTypes = Union[LoanSimulationResults, Any]
EntityOrList = Optional[Union[ResultTypes, List[ResultTypes]]]
ValidatorMethod = Callable[[Merchant], EntityOrList]
MerchantAndResult = Tuple[Merchant, EntityOrList]


class MerchantFactory:
    def __init__(self, data_generator: DataGenerator, context: SimulationContext):
        self.data_generator = data_generator
        self.context = context

    def generate_diff_validator(self, conditions: List[MerchantCondition]) -> ValidatorMethod:
        lsr_validator = self.generate_lsr_validator(conditions)

        def validator(merchant: Merchant) -> EntityOrList:
            lsr = lsr_validator(merchant)
            if lsr is None:
                return None
            if len(lsr) > len(set(lsr)):
                return None
            return lsr

        return validator

    def generate_lsr_validator(
            self, conditions: Union[MerchantCondition, List[MerchantCondition]]) -> \
            ValidatorMethod:
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
                    if conditions[i].min_value is not None and value < conditions[
                        i].min_value + constants.FLOAT_ADJUSTMENT:
                        return None
                    if conditions[i].max_value is not None and value > conditions[
                        i].max_value - constants.FLOAT_ADJUSTMENT:
                        return None
            return [loan.simulation_results for loan in loans] if len(loans) > 1 else loans[0].simulation_results

        return validator

    def generate_merchants(self, validator: Optional[ValidatorMethod] = None, num_merchants: Optional[int] = None) \
            -> List[Union[MerchantAndResult, Merchant]]:
        num_merchants = num_merchants or self.data_generator.num_merchants
        if validator is None:
            return [Merchant.generate_simulated(self.data_generator) for _ in range(num_merchants)]
        if num_merchants > 1:
            merchants_and_results = TqdmParallel(desc='Generating merchants', total=num_merchants)(
                delayed(self.merchant_generation_iteration)(validator) for _ in range(num_merchants))
            return merchants_and_results
        else:
            return [self.merchant_generation_iteration(validator)]

    def merchant_generation_iteration(self, validator: ValidatorMethod) -> MerchantAndResult:
        while True:
            merchant = Merchant.generate_simulated(self.data_generator)
            result = validator(merchant)
            if result:
                return merchant, result
