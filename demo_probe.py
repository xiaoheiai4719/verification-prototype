"""Only runs this package's fictional fixture. No arbitrary repo execution."""
import json
import sys
from examples.upload.service import FakeStorage, upload, upload_fixed
variant, scenario = sys.argv[1:]
fn = upload if variant == 'baseline' else upload_fixed
storage = FakeStorage(lose_first=scenario == 'lost_response')
identifier = fn(storage, 'fictional-image', 'request-001')
passed = len(storage.objects) == 1 and identifier == 1
print(json.dumps({'scenario': scenario, 'object_count': len(storage.objects),
                  'returned_id': identifier, 'expected_count': 1, 'passed': passed}))
sys.exit(0 if passed else 1)
