import matplotlib.pyplot as plt
import pandas as pd
def create_yield_chart():
    data = pd.read_csv('process_trial.csv')
    processes = ['old', 'new']
    yields = [data[data['process'] == p]['passed'].values[0] / data[data['process'] == p]['inspected'].values[0] for p in processes]

    plt.figure(figsize=(8, 6))
    plt.bar(processes, yields)
    plt.xlabel('Process')
    plt.ylabel('Yield Rate')
    plt.title('Yield Rate Comparison between Old and New Processes')
    plt.ylim(0, 1)
    plt.savefig('yield_chart.png')

create_yield_chart()
