"""Print original exported record IDs and fields for cited logical CSV rows."""
import argparse
import json
from common import read_tables, verify_snapshot


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('sources',nargs='+',help='Example: nodes_transactions.csv:row:1')
    args=parser.parse_args()
    index={r['_source']:r for rows in read_tables().values() for r in rows}
    for source in args.sources:
        if source.startswith('manifest:'):
            name=source.removeprefix('manifest:')
            manifest=verify_snapshot()
            if name not in manifest['files']: parser.error(f'Unknown table: {name}')
            print(json.dumps(dict(snapshot_id=manifest['snapshot_id'],table=name,**manifest['files'][name]),indent=2))
            continue
        if source not in index: parser.error(f'Unknown source ID: {source}')
        print(json.dumps(index[source],indent=2,ensure_ascii=True))
