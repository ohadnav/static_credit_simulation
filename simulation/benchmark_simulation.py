from __future__ import annotations

import os.path
from dataclasses import is_dataclass, fields
from typing import List, Hashable, Tuple, Mapping, Optional, MutableMapping

import pandas as pd

from common.local_enum import LoanSimulationType, LoanReferenceType
from common.local_numbers import Dollar, Float, O
from common.util import flatten
from scenario import Scenario
from simulation.merchant_factory import Condition
from simulation.simulation import Simulation

RISK_ORDER_COLUMN = 'risk_orders'
ATTRIBUTE_COLUMN = 'attribute'

BENCHMARK_LOAN_TYPES = [
    LoanSimulationType.INCREASING_REBATE,
    LoanSimulationType.INVOICE_FINANCING
]
PREDEFINED_SCENARIOS = [
    Scenario([Condition('annual_top_line', min_value=Dollar(10 ** 5), max_value=Dollar(10 ** 6))]),
    Scenario([Condition('annual_top_line', max_value=Dollar(10 ** 5))]),
    Scenario([Condition('annual_top_line', min_value=Dollar(10 ** 6))]),
    Scenario(volatile=True)
]


class BenchmarkSimulation(Simulation):
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
            correlations_df[lender_id].index.name = ATTRIBUTE_COLUMN
        results_df.index.name = ATTRIBUTE_COLUMN
        return results_df, correlations_df

    def risk_order_comparison(self) -> pd.DataFrame:
        risk_order_dict = {}
        for i in range(len(self.lenders)):
            risk_order_dict[self.lenders[i].loan_type.name] = self.lenders[i].risk_order_counts()
            risk_order_dict[f'{self.lenders[i].loan_type.name}_lender_profit'] = [str(p) for p in
                self.lenders[i].lender_profit_per_risk_order()]
        risk_order_df = pd.DataFrame(risk_order_dict, index=self.lenders[0].risk_order.risk_orders)
        risk_order_df.index.name = RISK_ORDER_COLUMN
        return risk_order_df

    def post_simulation(self):
        super(BenchmarkSimulation, self).post_simulation()
        results_df, correlations_df = self.to_dataframe()
        risk_order_df = self.risk_order_comparison()
        print(results_df.head())
        if self.save_dir:
            self.save_results(correlations_df, results_df, risk_order_df)

    def save_results(self, correlations_df, results_df, risk_order_df):
        results_df.to_csv(BenchmarkSimulation.results_filename(self.save_dir))
        risk_order_df.to_csv(BenchmarkSimulation.risk_order_filename(self.save_dir))
        for lender_id, corr_df in correlations_df.items():
            corr_df.to_csv(BenchmarkSimulation.correlations_filename(self.save_dir, LoanSimulationType[lender_id]))

    @staticmethod
    def results_filename(save_dir: str) -> str:
        return f'{save_dir}/results.csv'

    @staticmethod
    def risk_order_filename(save_dir: str) -> str:
        return f'{save_dir}/risk_orders.csv'

    @staticmethod
    def correlations_filename(save_dir: str, loan_type: LoanSimulationType) -> str:
        return f'{save_dir}/corr_{loan_type.name}.csv'


class BenchmarkSimulationAggregator:
    def __init__(self, run_dir: Optional[str] = None):
        self.run_dir = run_dir or Simulation.generate_run_dir()
        self.scenarios = flatten(
            [Scenario.generate_scenario_variants(generic_scenario, BENCHMARK_LOAN_TYPES, True) for generic_scenario in
                PREDEFINED_SCENARIOS])
        if not run_dir:
            for scenario in self.scenarios:
                if not scenario.loan_reference_type:
                    scenario.loan_simulation_types = LoanSimulationType.list()
                BenchmarkSimulation(scenario, self.run_dir, BENCHMARK_LOAN_TYPES)
        self.results_summary()

    def results_summary(self):
        self.calculate_non_reference_ratio()
        self.calculate_reference_ratio()
        self.aggregate_results()

    def aggregate_results(self):
        self.aggregate_risk_order()
        self.aggregate_correlations()

    def aggregate_risk_order(self):
        cols_to_read = [loan_type.name for loan_type in BENCHMARK_LOAN_TYPES]
        cols_to_read.append(RISK_ORDER_COLUMN)
        risk_order_dfs = [pd.read_csv(
            BenchmarkSimulation.risk_order_filename(scenario.get_dir(self.run_dir)), index_col=RISK_ORDER_COLUMN,
            usecols=cols_to_read)
            for scenario in self.scenarios_to_aggregate() if
            os.path.exists(BenchmarkSimulation.risk_order_filename(scenario.get_dir(self.run_dir)))]
        if RISK_ORDER_COLUMN in risk_order_dfs[0].columns:
            for i in range(len(risk_order_dfs)):
                risk_order_dfs[i].set_index(RISK_ORDER_COLUMN, inplace=True)
        agg_df = sum(risk_order_dfs)
        relative_df = (100.0 * agg_df / agg_df[BENCHMARK_LOAN_TYPES[0].name].sum()).round(1)
        relative_df.to_csv(f'{self.run_dir}/risk_order_summary.csv')

    def scenarios_to_aggregate(self) -> List[Scenario]:
        return [scenario for scenario in self.scenarios if
            scenario.loan_reference_type in [None, LoanReferenceType.TOTAL_INTEREST, LoanReferenceType.ANNUAL_REVENUE]]

    def aggregate_correlations(self):
        mean_corr_dfs: MutableMapping[LoanSimulationType, pd.DataFrame] = {}
        for loan_type in BENCHMARK_LOAN_TYPES:
            corr_dfs = [
                pd.read_csv(
                    BenchmarkSimulation.correlations_filename(scenario.get_dir(self.run_dir), loan_type), index_col=0)
                for scenario in self.scenarios_to_aggregate() if
                os.path.exists(BenchmarkSimulation.correlations_filename(scenario.get_dir(self.run_dir), loan_type))]
            mean_corr_dfs[loan_type] = (sum(corr_dfs) / len(corr_dfs)).round(3)
            mean_corr_dfs[loan_type].to_csv(f'{self.run_dir}/corr_{loan_type.name}.csv')
        for loan_type in BENCHMARK_LOAN_TYPES[1:]:
            relative_corr_df: pd.DataFrame = mean_corr_dfs[loan_type] / mean_corr_dfs[BENCHMARK_LOAN_TYPES[0]]
            relative_corr_df = relative_corr_df.fillna(0).round(2)
            relative_corr_df.to_csv(f'{self.run_dir}/relative_corr_{loan_type.name}.csv')

    def calculate_reference_ratio(self):
        for loan_reference_type in LoanReferenceType.list():
            reference_scenarios = [scenario for scenario in self.scenarios if
                scenario.loan_reference_type == loan_reference_type]
            self.calculate_scenario_ratio(reference_scenarios, loan_reference_type.name)

    def calculate_non_reference_ratio(self):
        non_reference_scenarios = [scenario for scenario in self.scenarios if scenario.loan_reference_type is None]
        self.calculate_scenario_ratio(non_reference_scenarios, 'non_reference')

    def calculate_scenario_ratio(self, scenarios: List[Scenario], summary_file_prefix: str):
        results_dfs = [pd.read_csv(BenchmarkSimulation.results_filename(scenario.get_dir(self.run_dir)), index_col=0)
            for scenario in scenarios if
            os.path.exists(BenchmarkSimulation.results_filename(scenario.get_dir(self.run_dir)))]
        ratio_df = self.calculate_results_ratio(results_dfs)
        ratio_df.to_csv(f'{self.run_dir}/{summary_file_prefix}_summary.csv')

    def calculate_results_ratio(self, results_dfs: List[pd.DataFrame]) -> pd.DataFrame:
        ratio_df = pd.DataFrame()
        for ind, _ in results_dfs[0].iterrows():
            for loan_type in results_dfs[0].columns[1:]:
                ratio_df.at[ind, loan_type] = str(
                    self.calculate_ratio_range_for_type(
                        LoanSimulationType[loan_type], results_dfs, ind, LoanSimulationType[results_dfs[0].columns[0]]))
        return ratio_df

    def calculate_ratio_range_for_type(
            self, evaluated_type: LoanSimulationType, results_dfs: List[pd.DataFrame], ind: Hashable,
            reference_type: LoanSimulationType) -> Float:
        ratios = []
        for results_df in results_dfs:
            if results_df.at[ind, reference_type.name] == 'None':
                continue
            for column in results_df.columns:
                if column != evaluated_type.name or reference_type.name not in results_df.columns \
                        or results_df.at[ind, column] == 'None':
                    continue
                reference_value = Float.from_human_format(results_df.at[ind, reference_type.name])
                evaluated_value = Float.from_human_format(results_df.at[ind, column])
                if reference_value > O and evaluated_value > O:
                    ratios.append(evaluated_value / reference_value)
                elif reference_value == O and evaluated_value == O:
                    ratios.append(O)
        return Float.mean(ratios)
