"""Validate and restore a Hearth backup to a NEW folder. Never overwrite data."""
import argparse
import hashlib
import json
from pathlib import Path
import sqlite3
import zipfile

def restore(source,target):
    target=Path(target).resolve()
    if target.exists(): raise ValueError('Choose a new, nonexistent folder. Existing data is never overwritten.')
    with zipfile.ZipFile(source) as z:
        if z.testzip(): raise ValueError('The ZIP file is damaged.')
        names=z.namelist()
        if 'manifest.json' not in names or 'hearth.sqlite3' not in names: raise ValueError('This is not a Hearth backup.')
        manifest=json.loads(z.read('manifest.json'))
        if manifest.get('app')!='Hearth' or manifest.get('format')!=1: raise ValueError('Unsupported backup format.')
        if sum(f.file_size for f in z.infolist())>10*1024**3: raise ValueError('Backup exceeds the 10 GB restore limit.')
        for name in names:
            if name in ('manifest.json','hearth.sqlite3'): continue
            parts=Path(name).parts
            if len(parts)!=2 or parts[0]!='uploads' or len(parts[1])!=32 or any(c not in '0123456789abcdef' for c in parts[1]): raise ValueError('Unexpected path in backup.')
        target.mkdir(parents=True);(target/'uploads').mkdir()
        for name in names:
            if name=='manifest.json':continue
            dest=(target/name).resolve()
            if not dest.is_relative_to(target):raise ValueError('Unsafe backup path.')
            dest.write_bytes(z.read(name))
    con=sqlite3.connect(target/'hearth.sqlite3')
    try:
        if con.execute('PRAGMA integrity_check').fetchone()[0]!='ok':raise ValueError('Database integrity check failed.')
        for fid,digest in con.execute('SELECT id,digest FROM files'):
            path=target/'uploads'/fid
            if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest()!=digest:raise ValueError('An attachment is missing or damaged.')
    finally:con.close()
    return target

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('backup');parser.add_argument('new_folder')
    args=parser.parse_args();folder=restore(args.backup,args.new_folder)
    print(f'Restored and verified: {folder}')
    print(f'Open this restored workspace: python server.py --port 8767 --data-dir "{folder}"')
