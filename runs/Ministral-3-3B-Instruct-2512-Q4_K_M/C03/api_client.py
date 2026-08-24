class ApiClient:
    def __init__(self, transport, max_retries=2):
        self.transport = transport
        self.max_retries = max_retries
        self.cache = {}  # 캐싱을 다시 활성화

    def get(self, key):
        if key in self.cache:  # 캐시된 데이터 반환
            return self.cache[key]

        for attempt in range(self.max_retries + 1):  # max_retries + 1번 시도 (재시도 포함)
            try:
                status, data = self.transport(key)
                if status >= 400 and status < 500:  # 4xx는 재시도하지 않음
                    raise RuntimeError(f'HTTP {status}')
                elif status >= 500:  # 5xx는 재시도 대상
                    if attempt < self.max_retries:
                        continue  # 재시도 후 다시 시도
                    else:
                        raise RuntimeError(f'HTTP {status}')
                
                self.cache[key] = data  # 성공 시 캐싱
                return data
            except Exception as e:
                continue
        raise RuntimeError('Request failed after max retries')
