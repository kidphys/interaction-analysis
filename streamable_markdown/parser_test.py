from .parser import parse_text_to_dataframe
import pandas as pd

def test_parser__parse_text_to_dataframe():
    text = f"""
format: csv
dtypes: age=int, price=float, active=bool

name,age,price,active
A,30,9.5,true
B,20,5.0,false
"""
    df = parse_text_to_dataframe(text)
    assert df.equals(pd.DataFrame({
        'name': ['A', 'B'],
        'age': [30, 20],
        'price': [9.5, 5.0],
        'active': [True, False]
    }))