import pandas as pd

def make_feature(df, window=3):
    out = df.copy()
    # BUG: center=True leaks future observations
    # FIX: Use only past data for rolling mean
    out['ma'] = out['value'].rolling(window, min_periods=1).mean()
    return out

def split_time(df, train_end, valid_end):
    # intended: train date <= train_end; valid train_end < date <= valid_end; test > valid_end
    train = df[df['date'] <= train_end]
    valid = df[(df['date'] > train_end) & (df['date'] <= valid_end)]  # FIX: Remove overlap with train
    test = df[df['date'] > valid_end]  # FIX: Remove overlap with valid
    return train, valid, test
