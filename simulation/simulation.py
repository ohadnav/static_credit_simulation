from __future__ import annotations

import json
import os
import time
from copy import deepcopy
from dataclasses import fields, dataclass, is_dataclass
from shutil import copyfile
from typing import List, Mapping, Tuple, Optional

import pandas as pd

from common import constants
from common.context import SimulationContext, DataGenerator
from common.enum import LoanSimulationType, LoanReferenceType
from common.numbers import Dollar, Float
from common.util import shout_print
from finance.lender import Lender
from finance.loan_simulation import LoanSimulation
from simulation.merchant_factory import Condition, MerchantFactory


@dataclass(unsafe_hash=True)
class Scenario:
    conditions: Optional[List[Condition]] = None
    volatile: bool = False
    loan_simulation_types: Optional[List[LoanSimulationType]] = None
    loan_reference_type: Optional[LoanReferenceType] = None

    def __str__(self):
        to_join = []
        to_join.append('Volatile' if self.volatile else '')
        to_join.append(self.loan_reference_type.name if self.loan_reference_type else '')
        if self.conditions:
            to_join.extend([condition.__str__() for condition in self.conditions])
        return ' '.join(filter(None, to_join))

    def __repr__(self):
        return self.__str__()

    @staticmethod
    def generate_scenario_variants(scenario: Scenario) -> List[Scenario]:
        assert scenario.loan_simulation_types is None
        assert scenario.loan_reference_type is None
        scenarios = [scenario]
        for loan_reference_type in LoanReferenceType.list():
            reference_scenario = deepcopy(scenario)
            reference_scenario.loan_reference_type = loan_reference_type
            reference_scenario.loan_simulation_types = BENCHMARK_LOAN_TYPES
            if not reference_scenario.conditions:
                reference_scenario.conditions = []
            for loan_type in BENCHMARK_LOAN_TYPES:
                reference_scenario.conditions.append(
                    Condition.generate_from_loan_reference_type(loan_reference_type, loan_type))
            scenarios.append(reference_scenario)
        return scenarios


BENCHMARK_LOAN_TYPES = [
    LoanSimulationType.INCREASING_REBATE,
    LoanSimulationType.LINE_OF_CREDIT,
    LoanSimulationType.INVOICE_FINANCING
]

PREDEFINED_SCENARIOS = [
    Scenario([Condition('annual_top_line', min_value=Dollar(10 ** 5), max_value=Dollar(10 ** 6))]),
    Scenario([Condition('annual_top_line', max_value=Dollar(10 ** 5))]),
    Scenario([Condition('annual_top_line', min_value=Dollar(10 ** 6))]),
    Scenario([Condition('num_products', max_value=Float(3))]),
    Scenario(volatile=True)
]

class Simulation:
    def __init__(self, scenario: Scenario, save_dir: Optional[str] = None):
        self.scenario = scenario
        self.context = self.generate_context()
        self.data_generator = self.generate_data_generator()
        self.lenders = self.generate_lenders()
        self.save_dir = save_dir

    def generate_data_generator(self) -> DataGenerator:
        data_generator = DataGenerator.generate_data_generator(self.scenario.volatile)
        return data_generator

    def generate_context(self) -> SimulationContext:
        context = SimulationContext.generate_context()
        context.loan_reference_type = self.scenario.loan_reference_type if self.scenario.loan_reference_type else None
        return context

    @staticmethod
    def run_all_scenarios():
        time_str = str(round(time.time()))[3:]
        run_dir = f'{constants.OUT_DIR}/{time_str}'
        os.mkdir(run_dir)
        for generic_scenario in PREDEFINED_SCENARIOS:
            for scenario in Scenario.generate_scenario_variants(generic_scenario):
                shout_print(f'SIMULATING {scenario.__str__()}')
                scenario_dir = f'{run_dir}/{scenario.__str__()}'
                os.mkdir(scenario_dir)
                simulation = Simulation(scenario, scenario_dir)
                simulation.simulate()

    def simulate(self):
        for i in range(len(self.lenders)):
            if i > 0:
                self.lenders[i].reference_loans = self.lenders[0].loans
            self.lenders[i].simulate()
        self.compare()

    def generate_lenders(self) -> List[Lender]:
        factory = MerchantFactory(self.data_generator, self.context)
        results = factory.generate_from_conditions(self.scenario.conditions)
        merchants = results
        if self.scenario.conditions:
            merchants = [mnr[0] for mnr in results]
            if isinstance(results[0][1], list) and isinstance(results[0][1][0], LoanSimulation):
                lenders = []
                for i in range(len(results[0])):
                    loans = [mnr[1][i] for mnr in results]
                    lenders.append(Lender.generate_from_simulated_loans(loans))
                return lenders
        loan_types = self.scenario.loan_simulation_types or LoanSimulationType.list()
        return [Lender(self.context, self.data_generator, deepcopy(merchants), loan_type) for loan_type in loan_types]

    def to_dataframe(self) -> Tuple[pd.DataFrame, Mapping[str, pd.DataFrame]]:
        results_df = pd.DataFrame()
        correlations_df = {}
        for lender in self.lenders:
            lender_id = lender.loan_type.name
            correlations_df[lender_id] = pd.DataFrame()
            for field_name, field_value in vars(lender.simulation_results).items():
                if is_dataclass(field_value):
                    for nested_field in fields(field_value):
                        nested_name = f'{field_name}_{nested_field.name}'
                        if nested_field.name in lender.risk_correlation:
                            for risk_field, correlation in lender.risk_correlation[nested_field.name].items():
                                correlations_df[lender_id].at[nested_name, risk_field] = str(correlation)
                        nested_value = getattr(field_value, nested_field.name)
                        results_df.at[nested_name, lender_id] = str(nested_value)
                else:
                    results_df.at[field_name, lender_id] = str(field_value)
        return results_df, correlations_df

    def compare(self):
        results_df, correlations_df = self.to_dataframe()
        print(results_df)
        if self.save_dir:
            results_df.to_csv(f'{self.save_dir}/results.csv')
            # Using a JSON string
            with open(f'{self.save_dir}/data_generator.json', 'w') as outfile:
                json.dump(self.data_generator.__dict__, outfile)
            with open(f'{self.save_dir}/simulation_context.json', 'w') as outfile:
                json.dump(self.context.to_dict(), outfile)
            copyfile('./common/constants.py', f'{self.save_dir}/constants.txt')
            for lender_id, corr_df in correlations_df.items():
                corr_df.to_csv(f'{self.save_dir}/corr_{lender_id}.csv')
