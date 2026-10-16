"""Write precomputed solver history using the existing Excel layout."""

import pandas as pd


class ExcelResultWriter:
    def write(self, history, file_path):
        columns = ['Step', 'Result']
        df = pd.DataFrame(history, columns=columns)
        df.to_excel(file_path, index=False)
