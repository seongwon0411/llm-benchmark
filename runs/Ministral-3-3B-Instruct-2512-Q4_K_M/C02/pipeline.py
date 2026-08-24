import pandas as pd

def make_feature(df, window=3):
    out = df.copy()
        # 미래 정보 누수를 방지: center=False로 변경
    out['ma'] = out['value'].rolling(window, center=False, min_periods=1).mean()    return out

def split_time(df, train_end, valid_end):
    # intended: train date <= train_end; valid train_end < date <= valid_end; test > valid_end
    train = df[df['date'] <= train_end]
    valid = df[(df['date'] >= train_end) & (df['date'] <= valid_end)]  # overlap bug
    test = df[df['date'] >= valid_end]  # overlap bug
    return train, valid, test
