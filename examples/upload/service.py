class LostResponse(Exception):
    pass

class FakeStorage:
    """Test double: first save succeeds remotely, then its response is lost."""
    def __init__(self, lose_first=False):
        self.objects = []
        self.keys = {}
        self.lose_first = lose_first

    def put(self, payload, key=None):
        if key is not None and key in self.keys:
            return self.keys[key]
        identifier = len(self.objects) + 1
        self.objects.append(payload)
        if key is not None:
            self.keys[key] = identifier
        if self.lose_first:
            self.lose_first = False
            raise LostResponse('saved remotely; response lost')
        return identifier

def upload(storage, payload, request_id):
    for attempt in range(2):
        try:
            return storage.put(payload)  # BUG: retry has no stable identity
        except LostResponse:
            if attempt == 1:
                raise

def upload_fixed(storage, payload, request_id):
    for attempt in range(2):
        try:
            return storage.put(payload, key=request_id)
        except LostResponse:
            if attempt == 1:
                raise
