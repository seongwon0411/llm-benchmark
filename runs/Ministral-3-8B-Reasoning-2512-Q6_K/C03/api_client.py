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
                if status == 429 or (400 <= status < 500 and status != 429):
                    raise RuntimeError(f'HTTP {status}')
                self.cache[key] = data
                return data
            except Exception as e:
                last = e
                # Retry only for 429 or 5xx
                if last and isinstance(last, RuntimeError):
                    status_code = int(str(last).split('HTTP ')[1].split(' ')[0])
                    if status_code == 429 or (500 <= status_code < 600):
                        continue
                    else:
                        break
        if last:
                # Do not cache failed results and exit loop
                self.cache.pop(key, None)  # Clear any cached value for this key
                raise last
            else:
                return data
