import argparse
from datetime import datetime
from pathlib import Path
from .llm_client import FixtureClient,ReplayClient,from_environment
from .pipeline import run


def main():
    p=argparse.ArgumentParser(description='V6 traceable architecture analysis')
    p.add_argument('input',nargs='?',default='examples/sample_requirements.txt')
    p.add_argument('--output',default=None);p.add_argument('--profile');p.add_argument('--one-pass',action='store_true')
    group=p.add_mutually_exclusive_group();group.add_argument('--fixture');group.add_argument('--replay')
    p.add_argument('--probe',action='store_true')
    a=p.parse_args()
    llm=FixtureClient(a.fixture) if a.fixture else ReplayClient(a.replay) if a.replay else from_environment(a.profile)
    if a.probe:
        print(llm.test_connection());return
    out=a.output or str(Path('outputs')/datetime.now().strftime('%Y%m%d_%H%M%S_%f'))
    result=run(a.input,out,llm,not a.one_pass,print)
    print(f'Output: {out}; review={result.review_status}; validation issues={len(result.validation_issues)}')

if __name__=='__main__':main()
