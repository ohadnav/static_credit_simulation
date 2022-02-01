from __future__ import annotations

from dataclasses import is_dataclass, fields
from typing import List, Hashable, Tuple, Mapping

import pandas as pd

from common.local_enum import LoanSimulationType, LoanReferenceType
from common.local_numbers import Dollar, Float, FloatRange, O
from common.util import flatten
from scenario import Scenario
from simulation.merchant_factory import Condition
from simulation.simulation import Simulation

BENCHMARK_LOAN_TYPES = [
    LoanSimulationType.INCREASING_REBATE,
    LoanSimulationType.INVOICE_FINANCING
]
PREDEFINED_SCENARIOS = [
    Scenario([Condition('annual_top_line', min_value=Dollar(10 ** 5), max_value=Dollar(10 ** 6))]),
    Scenario([Condition('annual_top_line', max_value=Dollar(10 ** 5))]),
    # Scenario([Condition('annual_top_line', min_value=Dollar(10 ** 6))]),
    Scenario(volatile=True)
]


class BenchmarkSimulation(Simulation):
    @staticmethod
    def run_all_scenarios():
        run_dir = Simulation.generate_run_dir()
        all_scenarios = flatten(
            [Scenario.generate_scenario_variants(generic_scenario, BENCHMARK_LOAN_TYPES, True) for generic_scenario in
                PREDEFINED_SCENARIOS])
        for scenario in all_scenarios:
            if not scenario.loan_reference_type:
                scenario.loan_simulation_types = LoanSimulationType.list()
            BenchmarkSimulation(scenario, run_dir)
        BenchmarkSimulation.results_summary(run_dir, all_scenarios)

    @staticmethod
    def results_summary(run_dir: str, all_scenarios: List[Scenario]):
        BenchmarkSimulation.calculate_non_reference_ratio(all_scenarios, run_dir)
        BenchmarkSimulation.calculate_reference_ratio(all_scenarios, run_dir)

    @staticmethod
    def calculate_reference_ratio(all_scenarios: List[Scenario], run_dir: str):
        for loan_reference_type in LoanReferenceType.list():
            reference_scenarios = [scenario for scenario in all_scenarios if
                scenario.loan_reference_type == loan_reference_type]
            BenchmarkSimulation.calculate_scenario_ratio(reference_scenarios, run_dir, loan_reference_type.name)

    @staticmethod
    def calculate_non_reference_ratio(all_scenarios: List[Scenario], run_dir: str):
        non_reference_scenarios = [scenario for scenario in all_scenarios if scenario.loan_reference_type is None]
        BenchmarkSimulation.calculate_scenario_ratio(non_reference_scenarios, run_dir, 'non_reference')

    @staticmethod
    def calculate_scenario_ratio(scenarios: List[Scenario], run_dir: str, summary_file_prefix: str):
        results_dfs = [pd.read_csv(BenchmarkSimulation.results_filename(scenario.get_dir(run_dir)), index_col=0) for
            scenario in scenarios]
        ratio_df = BenchmarkSimulation.calculate_results_ratio(results_dfs)
        ratio_df.to_csv(f'{run_dir}/{summary_file_prefix}_summary.csv')

    @staticmethod
    def calculate_results_ratio(results_dfs: List[pd.DataFrame]) -> pd.DataFrame:
        ratio_df = pd.DataFrame()
        for ind, _ in results_dfs[0].iterrows():
            for loan_type in results_dfs[0].columns[1:]:
                ratio_df.at[ind, loan_type] = BenchmarkSimulation.calculate_ratio_range_for_type(
                    LoanSimulationType[loan_type], results_dfs, ind, LoanSimulationType[results_dfs[0].columns[0]])
        return ratio_df

    @staticmethod
    def calculate_ratio_range_for_type(
            evaluated_type: LoanSimulationType, results_dfs: List[pd.DataFrame], ind: Hashable,
            reference_type: LoanSimulationType) -> FloatRange:
        ratio_range = FloatRange()
        for results_df in results_dfs:
            for column in results_df.columns:
                if column == evaluated_type.name and reference_type.name in results_df.columns:
                    reference_value = Float.from_human_format(results_df.at[ind, reference_type.name])
                    evaluated_value = Float.from_human_format(results_df.at[ind, column])
                    if reference_value > O and evaluated_value > O:
                        ratio_range.update(evaluated_value / reference_value)
                    elif reference_value == O and evaluated_value == O:
                        ratio_range.update(O)
        return ratio_range

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

    def risk_order_comparison(self) -> pd.DataFrame:
        risk_order_dict = {'risk_orders': self.lenders[0].risk_order.risk_orders}
        for i in range(len(self.lenders)):
            risk_order_dict[self.lenders[i].loan_type.name] = self.lenders[i].risk_order_counts()
        return pd.DataFrame(risk_order_dict)

    def post_simulation(self):
        super(BenchmarkSimulation, self).post_simulation()
        results_df, correlations_df = self.to_dataframe()
        risk_order_df = self.risk_order_comparison()
        print(results_df.head())
        if self.save_dir:
            self.save_results(correlations_df, results_df, risk_order_df)

    def save_results(self, correlations_df, results_df, risk_order_df):
        results_df.to_csv(BenchmarkSimulation.results_filename(self.save_dir))
        risk_order_df.to_csv(f'{self.save_dir}/risk_orders.csv')
        for lender_id, corr_df in correlations_df.items():
            corr_df.to_csv(f'{self.save_dir}/corr_{lender_id}.csv')

    @staticmethod
    def results_filename(save_dir: str):
        return f'{save_dir}/results.csv'
