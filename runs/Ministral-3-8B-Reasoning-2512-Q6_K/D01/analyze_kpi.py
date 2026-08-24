import pandas as pd
import matplotlib.pyplot as plt

def analyze_data():
    # CSV 파일 읽기
    df = pd.read_csv('factory_kpi.csv')
    
    # 분석 결과 저장할 딕셔너리
    analysis_result = {
        'yearly_summary': None,
        'defect_trend': None,
        'downtime_trend': None,
        'pilot_comparison': None
    }
    
    # 연도별 요약 데이터 생성
    yearly_summary = df.groupby('year').agg({
        'units_inspected': 'sum',
        'defects': 'sum',
        'downtime_min': 'sum'
    }).reset_index()
    analysis_result['yearly_summary'] = [row.to_dict() for _, row in yearly_summary.iterrows()]

    
    # defects 트렌드 데이터 (convert to native Python types)
    defect_trend = {k: int(v) for k, v in df.groupby('year')['defects'].sum().items()}
    analysis_result['defect_trend'] = defect_trend
    
    # downtime 트렌드 데이터 (convert to native Python types)
    downtime_trend = {k: int(v) for k, v in df.groupby('year')['downtime_min'].sum().items()}
    analysis_result['downtime_trend'] = downtime_trend
    
    # pilot 여부에 따른 defect 및 downtime 비교
    pilot_df = df[df['pilot'] == True]
    non_pilot_df = df[df['pilot'] == False]
    
    pilot_comparison = {
        'pilot': {
            'defects': pilot_df['defects'].sum(),
            'downtime_min': pilot_df['downtime_min'].sum()
        },
        'non_pilot': {
            'defects': non_pilot_df['defects'].sum(),
            'downtime_min': non_pilot_df['downtime_min'].sum()
        }
    }
    analysis_result['pilot_comparison'] = pilot_comparison
    
    # 트렌드 차트 생성
    plt.figure(figsize=(10, 5))
    years = [2024, 2025, 2026]
    defects = [df[df['year'] == year]['defects'].sum() for year in years]
    downtime = [df[df['year'] == year]['downtime_min'].sum() for year in years]
    
    plt.plot(years, defects, marker='o', label='Defects')
    plt.plot(years, downtime, marker='o', label='Downtime (min)')
    plt.xlabel('Year')
    plt.ylabel('Value')
    plt.title('Trend of Defects and Downtime Over Years')
    plt.legend()
    plt.grid(True)
    
    # 차트 저장
    plt.savefig('trend.png', dpi=300, bbox_inches='tight')
    plt.close()
    
    return analysis_result

if __name__ == "__main__":
    result = analyze_data()
    
    # JSON 직렬화 함수 추가
    def pandas_to_json_serializable(obj):
        if isinstance(obj, pd.Series):
            return obj.tolist()
        elif isinstance(obj, pd.DataFrame):
            return obj.to_dict(orient='records')
        else:
            return obj
    
    # Ensure all numeric values are native Python types before writing to JSON
    def convert_to_native_types(obj):
        if isinstance(obj, dict):
            return {k: convert_to_native_types(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [convert_to_native_types(item) for item in obj]
        elif hasattr(obj, 'dtype') and np.issubdtype(obj.dtype, np.number):
            return int(obj)
        else:
            return obj
    
    # Convert all numeric values to native Python types
    result = convert_to_native_types(result)
    
    # JSON 파일 생성
    with open('analysis.json', 'w') as f:
        import json
        json.dump(result, f, indent=4)
    
    # yearly_summary.csv 파일 생성
    yearly_df = pd.DataFrame(result['yearly_summary'])
    yearly_df.to_csv('yearly_summary.csv', index=False)