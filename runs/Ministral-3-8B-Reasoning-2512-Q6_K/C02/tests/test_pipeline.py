import pandas as pd
from pipeline import make_feature, split_time

def test_no_future_leakage():
    df = pd.DataFrame({'value':[10,20,30,1000]})
    x = make_feature(df, 3)
    # at index 1 only [10,20] may be visible -> 15, not 20 from centered [10,20,30]
    assert abs(float(x.loc[1,'ma']) - 15.0) < 1e-9

def test_rolling_at_index_2():
    df = pd.DataFrame({'value':[10,20,30,1000]})
    x = make_feature(df, 3)
    assert abs(float(x.loc[2,'ma']) - 20.0) < 1e-9

def test_disjoint_splits():
    df = pd.DataFrame({'date':pd.to_datetime(['2026-01-01','2026-01-02','2026-01-03','2026-01-04'])})
    tr,va,te = split_time(df, pd.Timestamp('2026-01-02'), pd.Timestamp('2026-01-03'))
    assert list(tr['date'].dt.day) == [1,2]
    assert list(va['date'].dt.day) == [3]
    assert list(te['date'].dt.day) == [4]
    assert set(tr.index).isdisjoint(va.index)
    assert set(va.index).isdisjoint(te.index)
