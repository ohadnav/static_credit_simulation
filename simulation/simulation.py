import dataclasses
import time
from dataclasses import fields
from typing import List

import pandas as pd
from tqdm import tqdm

from common import constants
from common.context import SimulationContext, DataGenerator
from finance.lender import Lender
from seller.merchant import Merchant


class Simulation:
    def __init__(self, contexts: List[SimulationContext], data_generator: DataGenerator):
        self.contexts = contexts
        self.data_generator = data_generator
        self.merchants = self.generate_merchants()
        self.lenders: List[Lender] = [Lender(context, self.merchants) for context in
                                      self.contexts]
        self.to_save = False

    def generate_merchants(self) -> List[Merchant]:
        return [Merchant.generate_simulated(self.data_generator) for _ in range(constants.NUM_SIMULATED_MERCHANTS)]

    def simulate(self):
        for lender in tqdm(self.lenders, desc='Simulating..'):
            lender.simulate()

    def to_dataframe(self) -> pd.DataFrame:
        results_df = pd.DataFrame()
        for lender, result in self.lenders:
            lender_id = f'{lender.id}_{lender.context.loan_type}'
            for field in fields(lender.simulation_results):
                column_name = field.name
                value = getattr(lender.simulation_results, field.name)
                if dataclasses.is_dataclass(value):
                    for nested_field in fields(value):
                        nested_name = f'{column_name}.{nested_field.name}'
                        nested_value = getattr(value, nested_field.name)
                        results_df.at[lender_id, nested_name] = nested_value
                else:
                    results_df.at[lender.id, column_name] = value
        return results_df

    def compare(self):
        # TODO: correlation between underwriting parameter and Lender performance
        self.simulate()
        results_df = self.to_dataframe()
        print(results_df)
        if self.to_save:
            results_df.to_csv(f'{constants.OUT_DIR}/results_{time.time()}.csv')
