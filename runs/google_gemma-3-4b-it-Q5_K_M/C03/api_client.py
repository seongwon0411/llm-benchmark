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
                if status >= 400:
                    raise RuntimeError(f'HTTP {status}')
                self.cache[key] = data
                return data
            except Exception as e:
                last = e
                # BUG: retries every 4xx and arbitrary exception
                continue
        # BUG: failed result is cached as None
        self.cache[key] = None
        raise last
