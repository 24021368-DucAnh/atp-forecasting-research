from dataclasses import replace
from hashlib import sha256
import shutil
import pytest

T1 = '2026-11-28T10:00:00Z'
T2 = '2026-11-28T11:00:00Z'


def obs(payload=b'one', **changes):
    from atp_lab.intake.observations import Observation
    values = dict(source_id='SYN-feed', endpoint_id='SYN-results',
        payload_sha256=sha256(payload).hexdigest(), observed_at=T1,
        schema_version='v1', revision=1)
    values.update(changes)
    return Observation(**values)


def store(tmp_path):
    from atp_lab.intake.observations import ObservationStore
    root = tmp_path/'synthetic_intake'; root.mkdir()
    return ObservationStore(root)


def test_snapshot_replay_correction_restart_and_backup(tmp_path):
    from atp_lab.intake.observations import ObservationStore
    s = store(tmp_path); first = obs()
    assert s.append(first, b'one') == first.observation_id
    assert s.append(first, b'one') == first.observation_id
    assert s.append(replace(first, observed_at=T2), b'one') == first.observation_id
    assert len(s.inventory()) == 1
    second = obs(b'two', observed_at=T2, revision=2, previous_id=first.observation_id)
    assert s.append(second, b'two') == second.observation_id
    assert set(s.inventory()) == {first.observation_id, second.observation_id}
    assert s.read(first.observation_id) == first
    assert s.read(second.observation_id).available_at is None
    assert ObservationStore(s.root).read(second.observation_id) == second
    backup = tmp_path/'backup'/'synthetic_intake'; shutil.copytree(s.root, backup)
    assert ObservationStore(backup).inventory() == s.inventory()


@pytest.mark.parametrize('change', [{'source_id':'REAL-feed'}, {'revision':True},
    {'revision':2}, {'observed_at':'2026-11-28'}, {'available_at':T2},
    {'provider_event_at':'invalid'}, {'endpoint_id':'../outside'}, {'schema_version':''}])
def test_invalid_observation_leaves_store_empty(tmp_path,change):
    s = store(tmp_path)
    with pytest.raises(ValueError): s.append(obs(**change), b'one')
    assert s.inventory() == ()


def test_conflicting_same_revision_and_corrupt_payload(tmp_path):
    s = store(tmp_path); first = obs(); s.append(first,b'one')
    with pytest.raises(ValueError): s.append(obs(b'two'),b'two')
    with pytest.raises(ValueError): s.append(first,b'bad')
    (s.root/(first.payload_sha256+'.bin')).write_bytes(b'bad')
    with pytest.raises(ValueError): s.read(first.observation_id)


def test_interruption_orphan_is_not_an_observation(tmp_path,monkeypatch):
    from atp_lab.intake import observations as m
    s = store(tmp_path); first = obs(); publish = m._publish
    def interrupted(path, payload):
        if path.name.endswith('.receipt.json'): raise OSError('interrupted')
        return publish(path,payload)
    monkeypatch.setattr(m,'_publish',interrupted)
    with pytest.raises(OSError): s.append(first,b'one')
    assert s.inventory() == ()
    monkeypatch.setattr(m,'_publish',publish)
    assert m.ObservationStore(s.root).append(first,b'one') == first.observation_id


def test_wrong_mode_nonempty_directory_and_unsafe_path(tmp_path):
    from atp_lab.intake.observations import ObservationStore
    root=tmp_path/'synthetic_intake';root.mkdir();(root/'existing.sqlite').write_bytes(b'not ours')
    with pytest.raises(ValueError): ObservationStore(root)
    assert (root/'existing.sqlite').read_bytes()==b'not ours'
    with pytest.raises(ValueError): ObservationStore(root/'..'/'synthetic_intake')
    with pytest.raises(ValueError): ObservationStore('synthetic_intake')


def test_wrong_mode_marker_denied(tmp_path):
    from atp_lab.intake.observations import ObservationStore
    s=store(tmp_path); (s.root/'MODE').write_text('REAL')
    with pytest.raises(ValueError): ObservationStore(s.root)


def test_missing_predecessor_after_backup_is_not_a_valid_ledger(tmp_path):
    s=store(tmp_path); first=obs(); s.append(first,b'one')
    second=obs(b'two',revision=2,observed_at=T2,previous_id=first.observation_id)
    s.append(second,b'two')
    (s.root/(first.observation_id+'.receipt.json')).unlink()
    with pytest.raises(ValueError): s.inventory()
