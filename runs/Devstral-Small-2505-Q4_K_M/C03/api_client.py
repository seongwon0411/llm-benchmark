class ApiClient:
    def __init__(self, transport, max_retries=2):
        self.transport = transport
        self.max_retries = max_retries
        self.cache = {}

    def get(self, key):
        if key in self.cache:
            return self.cache[key]
        last = None
        for _ in range(self.max_retries + 1):
            try:
                status, data = self.transport(key)
                if status >= 400 and (status != 429 and not status // 100 == 5):
                    raise RuntimeError(f'HTTP {status}')
                self.cache[key] = data
                return data
            except Exception as e:
                last = e
                # Only retry on HTTP 429 or server errors (5xx)
                if isinstance(e, RuntimeError) and ('HTTP 429' in str(e) or 'HTTP 5' in str(e)):
                    continue
                break
        raise last
