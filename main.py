from common import constants
from simulation.simulation import Simulation


def main():
    constants.NUM_SIMULATED_MERCHANTS = 1
    Simulation.run_all_scenarios()


if __name__ == '__main__':
    main()
