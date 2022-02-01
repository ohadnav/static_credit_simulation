import os

from common.local_enum import RuntimeType
from simulation.benchmark_simulation import BenchmarkSimulation
from simulation.timeline_simulation import TimelineSimulation


def benchmark_simulation():
    BenchmarkSimulation.run_all_scenarios()


def plot_timeline():
    # TimelineSimulation.run_main_scenario()
    TimelineSimulation.run_reference_scenarios()


def main():
    if RuntimeType.BENCHMARK_SIMULATION.name == os.environ['RUNTIME_TYPE']:
        benchmark_simulation()
    if RuntimeType.PLOT_TIMELINE.name == os.environ['RUNTIME_TYPE']:
        plot_timeline()


if __name__ == '__main__':
    main()

