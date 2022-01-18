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
from common.enum import LoanSimulationType
from common.numbers import Dollar, Float
from common.util import shout_print
from finance.lender import Lender
from simulation.merchant_factory import Condition, MerchantFactory


@dataclass(unsafe_hash=True)
class Scenario:
    conditions: Optional[List[Condition]] = None
    volatile: bool = False

    def __str__(self):
        s = 'Volatile ' if self.volatile else ''
        if self.conditions:
            s += ' & '.join([condition.__str__() for condition in self.conditions])
        return s

    def __repr__(self):
        return self.__str__()


PREDEFINED_SCENARIOS = [
    Scenario([Condition('annual_top_line', max_value=Dollar(10 ** 5))]),
    Scenario([Condition('annual_top_line', min_value=Dollar(10 ** 6))]),
    Scenario([Condition('annual_top_line', min_value=Dollar(10 ** 5), max_value=Dollar(10 ** 6))]),
    Scenario([Condition('num_products', max_value=Float(3))]),
    Scenario(volatile=True)
]

IGNORE_VOLATILE = [
    'num_products_std',
    'cogs_margin_std',
    'sgna_rate_std',
    'manufacturing_duration_std',
    'first_batch_std_factor',
    'initial_stock_std',
    'price_std'
]


class Simulation:
    def __init__(self, scenario: Scenario, save_dir: Optional[str] = None):
        self.scenario = scenario
        self.context = SimulationContext.generate_context()
        self.data_generator = DataGenerator.generate_data_generator()
        if self.scenario.volatile:
            self.apply_volatile()
        self.lenders = self.generate_lenders()
        self.save_dir = save_dir

    @staticmethod
    def run_all_scenarios():
        time_str = str(round(time.time()))[3:]
        run_dir = f'{constants.OUT_DIR}/{time_str}'
        os.mkdir(run_dir)
        for scenario in PREDEFINED_SCENARIOS:
            shout_print(f'SIMULATING {scenario.__str__()}')
            scenario_dir = f'{run_dir}/{scenario.__str__()}'
            os.mkdir(scenario_dir)
            simulation = Simulation(scenario, scenario_dir)
            simulation.simulate()

    def apply_volatile(self):
        for key in dir(self.data_generator):
            if not key.startswith('_'):
                if 'std' in key and key not in IGNORE_VOLATILE:
                    value = getattr(self.data_generator, key)
                    setattr(self.data_generator, key, Float(value * 2))

    def simulate(self):
        for lender in self.lenders:
            lender.simulate()
        self.compare()

    def generate_lenders(self) -> List[Lender]:
        factory = MerchantFactory(self.data_generator, self.context)
        results = factory.generate_from_conditions(self.scenario.conditions)
        merchants = results
        if self.scenario.conditions:
            merchants = [mnr[0] for mnr in results]
        return [Lender(self.context, self.data_generator, deepcopy(merchants), loan_type) for loan_type in
            LoanSimulationType.list()]

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
                        results_df.at[lender_id, nested_name] = str(nested_value)
                else:
                    results_df.at[lender_id, field_name] = str(field_value)
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
