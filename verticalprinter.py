from tabulate import tabulate
import pandas as pd


def v(vlist):
    """Prints series, dataframes, and lists pretty"""
    vdf = pd.DataFrame(vlist)
    print(tabulate(vdf, headers='keys'))