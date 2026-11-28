"""Bounded, content-addressed offline observation ledger; single trusted writer."""
from dataclasses import asdict, dataclass, replace
from hashlib import sha256
import json
import os
from pathlib import Path
import re
import stat
import tempfile

from .policy import _clock, _digest, _hex, _id, _json

MAX_BYTES=1048576
MAX_RECEIPTS=4096
MODE=b'S8_SYNTHETIC_INTAKE_1\n'


def _safe(info):
    return not getattr(info,'st_file_attributes',0)&getattr(stat,'FILE_ATTRIBUTE_REPARSE_POINT',0x400)


def _read(path,limit):
    info=path.lstat()
    if not stat.S_ISREG(info.st_mode) or not _safe(info) or info.st_size>limit:
        raise ValueError('unsafe or oversized file')
    fd=os.open(path,os.O_RDONLY|getattr(os,'O_BINARY',0)|getattr(os,'O_NOFOLLOW',0))
    with os.fdopen(fd,'rb') as f:
        if not os.path.samestat(info,os.fstat(f.fileno())):
            raise ValueError('file changed during open')
        raw=f.read(limit+1)
    if len(raw)>limit: raise ValueError('oversized file')
    return raw


def _publish(path,payload):
    """No-clobber publication. An identical orphan may be reused."""
    if os.path.lexists(path):
        if _read(path,len(payload))!=payload: raise ValueError('immutable file conflict')
        return
    fd,name=tempfile.mkstemp(prefix='.s8-',dir=path.parent)
    try:
        with os.fdopen(fd,'wb') as f:
            f.write(payload);f.flush();os.fsync(f.fileno())
        try: os.link(name,path)
        except FileExistsError: pass
        if _read(path,len(payload))!=payload: raise ValueError('publication mismatch')
    finally:
        os.unlink(name)


@dataclass(frozen=True)
class Observation:
    source_id: str
    endpoint_id: str
    payload_sha256: str
    observed_at: str
    schema_version: str
    revision: int
    previous_id: str|None=None
    provider_event_at: str|None=None
    available_at: str|None=None

    @property
    def observation_id(self):
        return _digest(asdict(self))


def _validate(o):
    if (type(o) is not Observation or not _id(o.source_id) or not _id(o.endpoint_id)
        or not _hex(o.payload_sha256) or type(o.schema_version) is not str
        or not re.fullmatch(r'[A-Za-z0-9._-]{1,64}',o.schema_version)
        or type(o.revision) is not int or o.revision<1
        or (o.revision==1 and o.previous_id is not None)
        or (o.revision>1 and not _hex(o.previous_id))):
        raise ValueError('invalid synthetic observation')
    t=_clock(o.observed_at)
    if o.provider_event_at is not None: _clock(o.provider_event_at)
    if o.available_at is not None and _clock(o.available_at)>t:
        raise ValueError('availability later than receipt')


class ObservationStore:
    """Dedicated directory, not the accepted SQLite database. No real ingest."""
    def __init__(self,root):
        root=Path(root)
        if not root.is_absolute() or '..' in root.parts or root.name!='synthetic_intake':
            raise ValueError('explicit isolated synthetic_intake root required')
        for part in (root,*root.parents):
            info=part.lstat()
            if not stat.S_ISDIR(info.st_mode) or not _safe(info):
                raise ValueError('unsafe store path')
        self.root=root
        marker=root/'MODE'
        if not os.path.lexists(marker):
            if any(root.iterdir()): raise ValueError('nonempty unknown store')
            _publish(marker,MODE)
        self._check()

    def _check(self):
        if _read(self.root/'MODE',len(MODE))!=MODE: raise ValueError('wrong store mode')

    def read(self,observation_id):
        self._check()
        if not _hex(observation_id): raise ValueError('invalid receipt ID')
        raw=_read(self.root/(observation_id+'.receipt.json'),4096)
        try:
            o=Observation(**json.loads(raw));_validate(o)
            if o.observation_id!=observation_id or _json(asdict(o))!=raw:
                raise ValueError('receipt digest mismatch')
        except (TypeError,ValueError,KeyError) as exc:
            raise ValueError('invalid receipt') from exc
        payload=_read(self.root/(o.payload_sha256+'.bin'),MAX_BYTES)
        if sha256(payload).hexdigest()!=o.payload_sha256: raise ValueError('payload corruption')
        return o

    def inventory(self):
        self._check()
        ids=[];streams={}
        for path in self.root.glob('*.receipt.json'):
            if len(ids)>=MAX_RECEIPTS: raise ValueError('receipt inventory exceeds bound')
            oid=path.name[:-len('.receipt.json')];o=self.read(oid);ids.append(oid)
            streams.setdefault((o.source_id,o.endpoint_id),[]).append(o)
        for stream in streams.values():
            last=None
            for i,o in enumerate(sorted(stream,key=lambda r:r.revision),1):
                if (o.revision!=i or o.previous_id!=(last.observation_id if last else None)
                    or (last is not None and o.observed_at<=last.observed_at)):
                    raise ValueError('invalid stored revision chain')
                last=o
        return tuple(sorted(ids))

    def append(self,o,payload):
        self._check();_validate(o)
        if type(payload) is not bytes or not 0<len(payload)<=MAX_BYTES or sha256(payload).hexdigest()!=o.payload_sha256:
            raise ValueError('invalid observation payload')
        ids=self.inventory(); prior=[]
        for oid in ids:
            old=self.read(oid)
            if (old.source_id,old.endpoint_id)==(o.source_id,o.endpoint_id): prior.append(old)
        for old in prior:
            if old.revision==o.revision:
                if replace(o,observed_at=old.observed_at)==old and o.observed_at>=old.observed_at:
                    return old.observation_id
                raise ValueError('conflicting immutable revision')
        last=max(prior,key=lambda r:r.revision) if prior else None
        if ((last is None and o.revision!=1) or (last is not None and
            (o.revision!=last.revision+1 or o.previous_id!=last.observation_id or o.observed_at<=last.observed_at))):
            raise ValueError('broken revision linkage')
        if len(ids)>=MAX_RECEIPTS: raise ValueError('store full')
        _publish(self.root/(o.payload_sha256+'.bin'),payload)
        _publish(self.root/(o.observation_id+'.receipt.json'),_json(asdict(o)))
        return o.observation_id
