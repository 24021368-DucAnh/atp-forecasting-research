"""P2.4 fixed ablation and exact-byte checkout regressions."""
from dataclasses import replace
from pathlib import Path
import random
import subprocess

import pytest

from atp_gate.tml_ablation import build_elo_variants, FEATURE_BLOCKS
from atp_gate.tml_development_features import FEATURE_NAMES
from atp_gate.tml_elo_experiment import _elo_p
from test_p2_2_pre_event_skill import m

ROOT=Path(__file__).resolve().parents[1]


def test_pinned_files_have_lf_checkout_contract():
    for name in ("p2_1r_tml_development_protocol_v1.json","p2_3_research_permission_v1.json"):
        path="docs/registries/"+name
        out=subprocess.check_output(["git","check-attr","eol","--",path],cwd=ROOT,text=True)
        assert out.strip().endswith(": eol: lf")
        assert b"\r" not in (ROOT/path).read_bytes()


def test_registered_feature_blocks():
    assert tuple(FEATURE_BLOCKS["elo_only"])==FEATURE_NAMES[:3]
    assert tuple(FEATURE_BLOCKS["elo_history"])==FEATURE_NAMES[:15]
    assert tuple(FEATURE_BLOCKS["all"])==FEATURE_NAMES


def test_variants_matured_batch_math_and_label_invariance():
    rows=[m("A1",1,"2023-01-01"),m("A1",2,"2023-01-01"),
          m("early",1,"2023-01-28"),m("late",1,"2023-01-29")]
    out=build_elo_variants(rows)
    assert set(out)=={"convex_surface","decay_k","mean_batch"}
    for p in out.values():
        assert p[rows[0].key]==p[rows[1].key]==p[rows[2].key]==.5
    key=rows[-1].key
    assert out["convex_surface"][key]==pytest.approx(_elo_p(48,0))
    assert out["decay_k"][key]==pytest.approx(_elo_p(2*250/(5**.4),0))
    assert out["mean_batch"][key]==pytest.approx(_elo_p(24,0))
    changed=[*rows[:-1],replace(rows[-1],outcome_a=0)]
    assert build_elo_variants(changed)==out
    random.Random(29).shuffle(rows)
    assert build_elo_variants(rows)==out
