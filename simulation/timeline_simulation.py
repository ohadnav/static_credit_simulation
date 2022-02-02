from copy import deepcopy
from dataclasses import fields
from typing import List, Mapping, Union, Tuple, Optional

import pandas as pd
import plotly.graph_objects as go
from plotly.graph_objs import Figure

from common import constants
from common.context import SimulationContext, DataGenerator
from common.local_enum import LoanSimulationType, LoanReferenceType
from common.local_numbers import Dollar, Duration, O, Float, Int, ONE_INT
from loan_simulation_results import AggregatedLoanSimulationResults
from scenario import Scenario
from simulation.merchant_factory import Condition
from simulation.simulation import Simulation

LOAN_TYPES = [
    LoanSimulationType.INCREASING_REBATE,
    LoanSimulationType.INVOICE_FINANCING
]
REFERENCE_TYPES = [LoanReferenceType.TOTAL_INTEREST, LoanReferenceType.ANNUAL_REVENUE]

SCENARIO = Scenario(
    [Condition('annual_top_line', min_value=Dollar(10 ** 5), max_value=Dollar(10 ** 6))],
    loan_simulation_types=LOAN_TYPES)

CREDIT_FIELDS = ['loan_amount', 'underutilized_credit', 'remaining_credit']


class TimelineSimulation(Simulation):
    @staticmethod
    def run_reference_scenarios():
        run_dir = Simulation.generate_run_dir()
        all_scenarios = Scenario.generate_scenario_variants(SCENARIO, LOAN_TYPES, False, REFERENCE_TYPES)
        for scenario in all_scenarios:
            TimelineSimulation(scenario, run_dir)

    @staticmethod
    def run_main_scenario():
        run_dir = Simulation.generate_run_dir()
        scenario = deepcopy(SCENARIO)
        for loan_type in LOAN_TYPES:
            scenario.conditions.append(Condition.generate_from_loan_type(loan_type))
        TimelineSimulation(scenario, run_dir)

    def generate_data_generator(self) -> DataGenerator:
        data_generator = super(TimelineSimulation, self).generate_data_generator()
        data_generator.account_suspension_chance = O
        return data_generator

    def generate_context(self) -> SimulationContext:
        context = super(TimelineSimulation, self).generate_context()
        if self.data_generator.num_merchants == 1:
            context.snapshot_cycle = ONE_INT
        else:
            context.snapshot_cycle = Duration(constants.WEEK)
        return context

    def post_simulation(self):
        super(TimelineSimulation, self).post_simulation()
        self.plot_timeline()
        self.plot_cost_to_cagr_graphs()
        self.plot_credit_evolution()

    def plot_credit_evolution(self):
        fig = go.Figure(layout_title_text='credit_evolution')
        for lender in self.lenders:
            for i, field in enumerate(CREDIT_FIELDS):
                snapshot_dates = [date for date in lender.snapshots.keys()]
                values = [getattr(lender.snapshots[day], field) for day in lender.snapshots.keys()]
                line_properties = dict(color='blue' if lender.loan_type == LOAN_TYPES[0] else 'red')
                if i > 0:
                    line_properties['dash'] = ['dash', 'dot'][i - 1]
                fig.add_trace(
                    go.Scatter(
                        x=snapshot_dates, y=values, mode='lines', name=f'{lender.loan_type.name}_{field}',
                        line=line_properties))
        self.show_and_save(fig)

    def plot_timeline(self):
        for field in fields(AggregatedLoanSimulationResults):
            results = {}
            fig = go.Figure(layout_title_text=field.name)
            for lender in self.lenders:
                values = [getattr(lender.snapshots[day], field.name) for day in lender.snapshots.keys()]
                if len(set(values)) <= 1:
                    continue
                results[f'{field.name}_{lender.loan_type.name}'] = values
                snapshot_dates = [date for date in lender.snapshots.keys()]
                # noinspection PyTypeChecker
                fig.add_trace(
                    go.Scatter(
                        x=snapshot_dates, y=values, mode='lines', name=lender.loan_type.name, line_shape='spline'))
                results[f'timeline'] = snapshot_dates
            if results:
                self.show_and_save(fig, results)

    def plot_cost_to_cagr_graphs(self):
        self.plot_x_to_y('total_interest', 'projected_cagr')
        self.plot_x_to_y('total_interest', 'revenue_cagr')
        self.plot_x_to_y('total_interest', 'annual_revenue')

    def plot_x_to_y(self, x_axis_name: str, y_axis_name: str):
        results = {}
        fig_x_to_y = go.Figure(layout_title_text=f'{x_axis_name}_to_{y_axis_name}')
        for lender in self.lenders:
            x_axis = [getattr(lender.snapshots[day], x_axis_name) for day in lender.snapshots.keys()]
            y_axis = [getattr(lender.snapshots[day], y_axis_name) for day in lender.snapshots.keys()]
            clean_x, clean_y = self.clean_and_sort_results(x_axis, y_axis, O, O)
            # noinspection PyTypeChecker
            fig_x_to_y.add_trace(
                go.Scatter(x=clean_x, y=clean_y, mode='lines', name=lender.loan_type.name, line_shape='spline'))
            results[f'{y_axis_name}_{lender.loan_type.name}'] = clean_y
            results[f'{x_axis_name}_{lender.loan_type.name}'] = clean_x
        self.show_and_save(fig_x_to_y, results, False)

    def clean_and_sort_results(self, x_axis: List[Float], y_axis: List[Float], min_x: Float, min_y: Float) -> Tuple[
        List[Float], List[Float]]:
        assert len(x_axis) == len(y_axis)
        clean_x = deepcopy(x_axis)
        clean_y = deepcopy(y_axis)
        for i in reversed(range(len(x_axis) - 1)):
            need_to_remove = x_axis[i] == x_axis[i + 1] or y_axis[i] <= min_y or x_axis[i] <= min_x
            if not need_to_remove:
                continue
            clean_x.pop(i)
            clean_y.pop(i)
        clean_y = [y for _, y in sorted(zip(clean_x, clean_y))]
        clean_x = sorted(clean_x)
        return clean_x, clean_y

    def show_and_save(
            self, fig: Figure, results: Optional[Mapping[str, List[Union[Float, Int]]]] = None, to_show=False):
        if to_show:
            fig.show()
        fig.write_image(f'{self.save_dir}/{fig.layout.title.text}.png')
        if results:
            try:
                # noinspection PyTypeChecker
                results_df = pd.DataFrame.from_dict(results)
                results_df.to_csv(f'{self.save_dir}/{fig.layout.title.text}.csv', index=False)
            except ValueError:
                self.save_json(results, f'{fig.layout.title.text}.json')
