"""Console formatting and output for already calculated solver results."""


class ConsolePresenter:
    def format_result(self, step, label, result, member):
        """Format scalar results and a route string without accessing a solver."""
        return ('PARTICLE SWARM: \n' +
                'CURRENT STEPS: %d \n' +
                'BEST %s: %f \n' +
                'BEST MEMBER: %s \n\n') % (
                    step, label, result, member)

    def present_result(self, text):
        """Display a formatted intermediate or final result."""
        print(text)

    def present_completion(self):
        print("TERMINATING - REACHED MAXIMUM STEPS")
