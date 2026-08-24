import matplotlib.pyplot as plt
import pandas as pd

def generate_mtbf_chart():
    # Read the CSV file
    df = pd.read_csv('maintenance_kpi.csv')
    
    # Calculate MTBF for each line
    df['mtbf'] = df['operating_hours'] / df['failures']
    
    # Create a bar chart
    plt.figure(figsize=(10, 6))
    plt.bar(df['line'], df['mtbf'])
    plt.xlabel('Line')
    plt.ylabel('MTBF (hours)')
    plt.title('Mean Time Between Failures for Each Line')
    
    # Save the chart as a PNG file
    plt.savefig('mtbf.png', dpi=300)
    
generate_mtbf_chart()
