import json
from stv_lebanon.lambda_function import lambda_handler

with open('sample.json') as f:
    sample = json.load(f)

res = lambda_handler(sample, None)

print(json.dumps(res, indent=2))
