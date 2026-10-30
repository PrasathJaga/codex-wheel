"""One authorized paid diagnosis of a pinned archived case; no rerun loop."""
import argparse
import json
import os
from pathlib import Path
from wheel.diagnosis import diagnose_archive

ARCHIVE_SHA = '611728f172308ef43344347ad87a797b32169d47179380a0a9c55f3d685a55c8'


def run(archive, output):
    output = Path(output)
    output.mkdir(exist_ok=False)
    key = os.environ.pop('MODEL_API_KEY', '')
    if not key:
        (output / 'status.json').write_text(json.dumps({'status': 'missing_credentials', 'new_model_calls': 0}))
        raise RuntimeError('MODEL_API_KEY is missing')
    from openai import OpenAI
    client = OpenAI(api_key=key, base_url='https://api.meta.ai/v1', max_retries=0, timeout=60)
    result = diagnose_archive(client, archive, ARCHIVE_SHA, 'clarified_interface-0', output / 'attempt.json')
    (output / 'status.json').write_text(json.dumps({
        'status': result['status'], 'new_model_calls': result['new_model_calls'],
        'numeric_usd_cost': None, 'dollar_cap': 'removed_by_owner',
        'max_requests': 1, 'max_completion_tokens': 2048,
        'automatic_retries': 0, 'semantic_review': 'required',
    }, indent=2))
    if result['status'] not in ('explained', 'abstained'):
        raise RuntimeError('Diagnosis did not pass; outcome preserved')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--archive', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    run(args.archive, args.output)
