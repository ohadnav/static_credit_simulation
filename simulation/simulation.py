from __future__ import annotations

import json
import os
import time
from abc import abstractmethod, ABC
from copy import deepcopy
from shutil import copyfile
from typing import List, Mapping

from common import constants
from common.context import SimulationContext, DataGenerator
from common.local_enum import LoanSimulationType
from common.util import shout_print, inherits_from
from finance.lender import Lender
from finance.loan_simulation import LoanSimulation
from merchant_factory import MerchantFactory, MerchantAndResult
from scenario import Scenario


class Simulation(ABC):
    def __init__(self, scenario: Scenario, run_dir: str):
        shout_print(f'SIMULATING {scenario.__str__()}')
        self.scenario = scenario
        self.context = self.generate_context()
        self.data_generator = self.generate_data_generator()
        self.lenders = self.generate_lenders()
        self.save_dir = scenario.get_dir(run_dir, to_make=True)
        self.simulate()

    def generate_data_generator(self) -> DataGenerator:
        data_generator = DataGenerator.generate_data_generator(self.scenario.volatile)
        return data_generator

    def generate_context(self) -> SimulationContext:
        context = SimulationContext.generate_context()
        context.loan_reference_type = self.scenario.loan_reference_type if self.scenario.loan_reference_type else None
        return context

    @staticmethod
    def generate_run_dir():
        time_str = str(round(time.time()))[3:]
        run_dir = f'{constants.OUT_DIR}/{time_str}'
        os.mkdir(run_dir)
        return run_dir

    def generate_lenders(self) -> List[Lender]:
        factory = MerchantFactory(self.data_generator, self.context)
        results = factory.generate_from_conditions(self.scenario.conditions)
        merchants = results
        if self.scenario.conditions:
            merchants = MerchantFactory.get_merchants_from_results(results)
            if isinstance(results[0][1], list) and inherits_from(type(results[0][1][0]), LoanSimulation.__name__):
                return self.generate_lenders_from_simulated_loans(results)
        loan_types = self.scenario.loan_simulation_types or LoanSimulationType.list()
        return [Lender(self.context, self.data_generator, deepcopy(merchants), loan_type) for loan_type in loan_types]

    def generate_lenders_from_simulated_loans(self, results: List[MerchantAndResult]) -> List[Lender]:
        lenders = []
        for i in range(len(results[0][1])):
            loans = [mnr[1][i] for mnr in results]
            lenders.append(Lender.generate_from_simulated_loans(loans))
        return lenders

    def simulate(self):
        for i in range(len(self.lenders)):
            if i > 0:
                self.lenders[i].set_reference(self.lenders[0])
            self.lenders[i].simulate()
        self.post_simulation()

    @abstractmethod
    def post_simulation(self):
        self.save_context_files()

    def save_context_files(self):
        # Using a JSON string
        self.save_json(self.data_generator.__dict__, 'data_generator.json')
        self.save_json(self.context.to_dict(), 'simulation_context.json')
        copyfile('./common/constants.py', f'{self.save_dir}/constants.txt')

    def save_json(self, to_save: Mapping, filename: str):
        with open(f'{self.save_dir}/{filename}', 'w') as outfile:
            json.dump(to_save, outfile)
