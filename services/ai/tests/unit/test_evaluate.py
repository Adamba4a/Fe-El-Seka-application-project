import pytest

from pipelines.training.evaluate import ranking_quality_score


def test_ranking_quality_score_all_top_picks_correct():
    group_ids = [1, 1, 2, 2]
    y_true = [0, 1, 1, 0]
    y_pred = [0.2, 0.9, 0.8, 0.3]
    assert ranking_quality_score(group_ids, y_true, y_pred) == 1.0


def test_ranking_quality_score_top_pick_wrong_counts_as_miss():
    group_ids = [1, 1]
    y_true = [1, 0]
    y_pred = [0.1, 0.9]  # predicted top is index 1 (label 0) -> miss
    assert ranking_quality_score(group_ids, y_true, y_pred) == 0.0


def test_ranking_quality_score_excludes_groups_with_no_actual_choice():
    group_ids = [1, 1, 2, 2]
    y_true = [0, 0, 1, 0]  # group 1 never had an actual choice -> excluded from denominator
    y_pred = [0.5, 0.5, 0.9, 0.1]
    assert ranking_quality_score(group_ids, y_true, y_pred) == 1.0


def test_ranking_quality_score_no_decided_groups_returns_zero():
    group_ids = [1, 1, 2, 2]
    y_true = [0, 0, 0, 0]
    y_pred = [0.5, 0.5, 0.9, 0.1]
    assert ranking_quality_score(group_ids, y_true, y_pred) == 0.0


def test_ranking_quality_score_mixed_groups_computes_hit_rate():
    group_ids = [1, 1, 2, 2, 3, 3]
    y_true = [1, 0, 0, 1, 1, 0]
    y_pred = [0.9, 0.1, 0.9, 0.1, 0.2, 0.8]  # group 1 hit, group 2 miss, group 3 miss
    assert ranking_quality_score(group_ids, y_true, y_pred) == pytest.approx(1 / 3)
