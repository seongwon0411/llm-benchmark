class ApiClient:
    def __init__(self, transport, max_retries=2):
        self.transport = transport
        self.max_retries = max_retries
        # Do NOT cache any responses to avoid accumulating stale data on 429/5xx errors

    def get(self, key):
        try:
            status, data = self.transport(key)
            if 400 <= status < 500:
                # Retry only for client-side errors (429) up to max_retries times
            retry_count = 0
def run_pytest(path):