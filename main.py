import os

from common.local_enum import RuntimeType
from simulation.benchmark_simulation import BenchmarkSimulationAggregator
from simulation.timeline_simulation import TimelineSimulation


def benchmark_simulation():
    BenchmarkSimulationAggregator()


def plot_timeline():
    TimelineSimulation.run_main_scenario()
    TimelineSimulation.run_reference_scenarios()


def main():
    runtime_type = os.environ['RUNTIME_TYPE']
    if runtime_type == RuntimeType.RUN_ALL.name or RuntimeType.BENCHMARK_SIMULATION.name == runtime_type:
        benchmark_simulation()
    if runtime_type == RuntimeType.RUN_ALL.name or RuntimeType.PLOT_TIMELINE.name == runtime_type:
        plot_timeline()


if __name__ == '__main__':
    main()
