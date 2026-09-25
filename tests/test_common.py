import pandas as pd

from common import counts_as_int


def test_counts_as_int_keeps_fractions_and_text():
    df = pd.DataFrame({
        "sq_ncloc": [7298.0, None],
        "sq_sqale_rating": [1.0, 3.0],
        "sq_comment_lines_density": [5.0, 6.0],
        "py_cc_avg": [2.0, 3.0],
        "py_mi_avg": [70.5, 60.0],
        "py_notes": ["a", None],
        "sq_ncloc_language_distribution": ["py=10;js=5", None],
    })
    out = counts_as_int(df.copy()).to_csv(index=False).splitlines()
    assert out[1] == "7298,1,5.0,2.0,70.5,a,py=10;js=5"
    assert out[2] == ",3,6.0,3.0,60.0,,"
