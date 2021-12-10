from IPython.core.display import display

def display_styled_table(df):
    """Pretty print dataframes as HTML tables for Jupyter."""
    df_style = df.style
    df_style.set_table_styles([
        {'selector': 'th.col_heading', 'props': 'text-align: left;'},
        {'selector': 'th.col_heading.level0', 'props': 'font-size: 1.2em;'},
        {'selector': 'td', 'props': 'text-align: left;'},
    ], overwrite=False)
    display(df_style)

