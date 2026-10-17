"""Desktop Experiment Runner, with the historical terminal interface available."""
import argparse


def main():
    """Parse CLI options and launch the desktop or terminal interface."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--terminal', action='store_true',
                        help='Open the legacy run/analysis terminal menu')
    args = parser.parse_args()
    # Load only the selected UI; --help needs neither GUI nor analysis dependencies.
    if args.terminal:
        from tsp_pso.presentation.terminal import main as start
    else:
        from tsp_pso.presentation.experiment_gui import main as start
    start()


if __name__ == '__main__':
    main()
