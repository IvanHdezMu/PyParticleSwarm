"""Desktop Experiment Runner."""
import argparse


def main():
    """Parse launch options and open the desktop interface."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.parse_args()
    # --help needs neither GUI nor analysis dependencies.
    from tsp_pso.presentation.experiment_gui import main as start
    start()


if __name__ == '__main__':
    main()
