#!/usr/bin/env python3
"""Install a new module release beneath usr/lib/modules; preserve /lib."""
import argparse
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import tarfile
import tempfile


def install(archive_path, root):
    root = Path(root).resolve()
    if not (root / 'lib').is_symlink() or os.readlink(root / 'lib') != 'usr/lib':
        raise ValueError('expected merged-/usr root: lib -> usr/lib')
    base = root / 'usr/lib/modules'
    if base.resolve() != base:
        raise ValueError('module destination must not traverse another symlink')
    with tarfile.open(archive_path) as archive:
        members = archive.getmembers()
        releases = set()
        for member in members:
            parts = PurePosixPath(member.name).parts
            if len(parts) < 3 or parts[:2] != ('lib', 'modules') or '..' in parts:
                raise ValueError('archive must contain only lib/modules/RELEASE/...')
            if not re.fullmatch(r'[A-Za-z0-9_+.-]+', parts[2]) or parts[2] in ('.', '..'):
                raise ValueError('invalid kernel release')
            if not (member.isfile() or member.isdir()):
                raise ValueError('links and devices are not module payloads')
            releases.add(parts[2])
        if len(releases) != 1:
            raise ValueError('expected exactly one module release')
        release = releases.pop()
        target = base / release
        if target.exists() or target.is_symlink():
            raise FileExistsError(target)
        base.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix='.modules-', dir=base) as temporary:
            staging = Path(temporary) / release
            staging.mkdir(mode=0o755)
            for member in members:
                relative = PurePosixPath(member.name).parts[3:]
                destination = staging.joinpath(*relative)
                if member.isdir():
                    destination.mkdir(parents=True, exist_ok=True, mode=0o755)
                else:
                    destination.parent.mkdir(parents=True, exist_ok=True, mode=0o755)
                    with archive.extractfile(member) as src, destination.open('xb') as dst:
                        shutil.copyfileobj(src, dst)
                    destination.chmod(0o644)
            staging.rename(target)
    return release


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('archive', type=Path)
    parser.add_argument('root', type=Path, help='mounted target root; / only for an intentional live install')
    args = parser.parse_args()
    if os.geteuid() != 0:
        parser.error('root required')
    print(install(args.archive, args.root))
