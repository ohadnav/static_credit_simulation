from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from typing import Callable, List, Optional, Union, Tuple

from joblib import delayed

from common.context import DataGenerator, SimulationContext
from common.enum import LoanSimulationType, LoanReferenceType
from common.numbers import Float, O
from common.util import TqdmParallel, LIVE_RATE
from finance import lender
from finance.loan_simulation import LoanSimulation
from seller.merchant import Merchant


@dataclass(unsafe_hash=True)
class Condition:
    field_name: Optional[str] = None
    loan_type: Optional[LoanSimulationType] = None
    min_value: Optional[Float] = None
    max_value: Optional[Float] = None

    def __str__(self):
        s = f'{self.loan_type.name} and ' if self.loan_type else ''
        if self.min_value is not None:
            if self.max_value is not None:
                s += f'{self.min_value.__str__()} < {self.field_name} < {self.max_value.__str__()}'
            else:
                s += f'{self.field_name} > {self.min_value.__str__()}'
        elif self.max_value is not None:
            s += f'{self.field_name} < {self.max_value.__str__()}'
        return s

    def __repr__(self):
        return self.__str__()

    @classmethod
    def generate_from_loan_reference_type(
            cls, loan_reference_type: LoanReferenceType, loan_type: LoanSimulationType) -> Condition:
        return Condition(loan_reference_type.name.lower(), loan_type, O)


ConditionsEntityOrList = Union[Condition, List[Condition]]
ResultsType = Union[LoanSimulation, Float]
EntityOrList = Optional[Union[ResultsType, List[ResultsType]]]
ValidatorMethod = Callable[[Merchant], EntityOrList]
MerchantAndResult = Tuple[Merchant, EntityOrList]


class MerchantFactory:
    def __init__(self, data_generator: DataGenerator, context: SimulationContext):
        self.data_generator = data_generator
        self.context = context

    def generate_merchant_validator(self, conditions: ConditionsEntityOrList) -> ValidatorMethod:
        if isinstance(conditions, Condition):
            conditions = [conditions]

        def validator(merchant: Merchant) -> EntityOrList:
            values: List[Float] = [getattr(merchant, condition.field_name)(self.data_generator.start_date) for condition
                in conditions]
            for i in range(len(conditions)):
                if conditions[i].min_value is not None and not values[i] > conditions[i].min_value:
                    return None
                if conditions[i].max_value is not None and not values[i] < conditions[i].max_value:
                    return None
            return values if len(values) > 1 else values[0]

        return validator

    def generate_diff_validator(self, conditions: ConditionsEntityOrList) -> ValidatorMethod:
        lsr_validator = self.generate_lsr_validator(conditions)

        def diff_validator(merchant: Merchant) -> EntityOrList:
            loans = lsr_validator(merchant)
            if loans is None:
                return None
            for i in range(1, len(loans)):
                if self.context.loan_reference_type is not None:
                    if not loans[i].loan_reference_diff.fast_diff(loans[i].today, loans[i].reference_loan.today):
                        return None
                else:
                    lsr = [loan.simulation_results for loan in loans]
                    if len(lsr) > len(set(lsr)):
                        return None
            return loans

        return diff_validator

    def generate_lsr_validator(self, conditions: ConditionsEntityOrList) -> ValidatorMethod:
        if isinstance(conditions, Condition):
            conditions = [conditions]

        def validator(merchant: Merchant) -> EntityOrList:
            loans: List[LoanSimulation] = []
            for i in range(len(conditions)):
                reference_loan = loans[0] if loans and self.context.loan_reference_type else None
                loans.append(
                    lender.Lender.generate_loan(
                        deepcopy(merchant), self.context, self.data_generator, conditions[i].loan_type, reference_loan))
                loans[i].simulate()
                if conditions[i].field_name:
                    value = getattr(loans[i].simulation_results, conditions[i].field_name)
                    if conditions[i].min_value is not None and not value > conditions[i].min_value:
                        return None
                    if conditions[i].max_value is not None and not value < conditions[i].max_value:
                        return None
                if reference_loan and conditions[i].loan_type != LoanSimulationType.NO_CAPITAL:
                    if not loans[i].compare_reference_loan():
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
            MerchantFactory.reset_id(merchants_and_results)
            return merchants_and_results
        else:
            return [self.merchant_generation_iteration(validator)]

    @staticmethod
    def reset_id(merchants_and_results: List[MerchantAndResult]):
        merchants = MerchantFactory.get_merchants_from_results(merchants_and_results)
        for merchant in merchants:
            merchant.reset_id()
            for inventory in merchant.inventories:
                inventory.reset_id()
                inventory.product.reset_id()
                for batch in inventory.batches:
                    batch.reset_id()

    @staticmethod
    def get_merchants_from_results(merchants_and_results: List[MerchantAndResult]) -> List[Merchant]:
        return [mnr[0] for mnr in merchants_and_results]

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

    def generate_validator(self, conditions: List[Condition]) -> ValidatorMethod:
        ensure_diff = len(set([condition.loan_type for condition in conditions if condition.loan_type is not None])) > 1
        lsr_conditions = [condition for condition in conditions if condition.loan_type is not None]
        merchant_conditions = [condition for condition in conditions if condition.loan_type is None]

        def validator_wrapper(merchant: Merchant) -> EntityOrList:
            merchant_validator = self.generate_merchant_validator(merchant_conditions) if merchant_conditions else None
            lsr_validator = self.generate_lsr_validator(lsr_conditions) if lsr_conditions else None
            if ensure_diff:
                lsr_validator = self.generate_diff_validator(lsr_conditions)
            if merchant_validator:
                merchant_validator_result = merchant_validator(merchant)
                if not merchant_validator_result:
                    return None
                if not lsr_validator:
                    return merchant_validator_result
            return lsr_validator(merchant)

        return validator_wrapper

    def generate_from_conditions(self, conditions: Optional[List[Condition]]) -> List[
        Union[MerchantAndResult, Merchant]]:
        if not conditions:
            return self.generate_merchants()
        validator = self.generate_validator(conditions)
        return self.generate_merchants(validator)
