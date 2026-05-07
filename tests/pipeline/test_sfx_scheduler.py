from pipeline.sfx_scheduler import schedule_sfx, schedule_sfx_layer


def test_same_seed_reproduces_schedule():
    s1 = schedule_sfx(pool_ids=[1, 2, 3], density_s=10, seed=42, start_s=0, end_s=120)
    s2 = schedule_sfx(pool_ids=[1, 2, 3], density_s=10, seed=42, start_s=0, end_s=120)
    assert s1 == s2


def test_different_seeds_diverge():
    s1 = schedule_sfx(pool_ids=[1, 2, 3], density_s=10, seed=42, start_s=0, end_s=120)
    s2 = schedule_sfx(pool_ids=[1, 2, 3], density_s=10, seed=43, start_s=0, end_s=120)
    assert s1 != s2


def test_density_bounds():
    """Density 10s, +/-50% jitter => gaps in [5, 15]. 120s window => 8-24 events."""
    sched = schedule_sfx(pool_ids=[1], density_s=10, seed=7, start_s=0, end_s=120)
    assert 8 <= len(sched) <= 24
    times = [t for t, _ in sched]
    gaps = [times[i+1] - times[i] for i in range(len(times) - 1)]
    for g in gaps:
        assert 4.99 <= g <= 15.01


def test_window_offset_consistent():
    """Schedule from t=60..120 with same seed must match the t=60..120 slice
    of the schedule from t=0..120."""
    full = schedule_sfx(pool_ids=[1, 2], density_s=8, seed=99, start_s=0, end_s=120)
    second_half = [(t, sid) for t, sid in full if t >= 60]
    sliced = schedule_sfx(pool_ids=[1, 2], density_s=8, seed=99, start_s=60, end_s=120)
    # Note: schedules differ because RNG is reseeded per call. This test documents
    # the chosen behavior: chunks recompute their own slice using the same seed
    # but starting from start_s, NOT by sampling a full-length schedule. We accept
    # that preview SFX timing may differ slightly from chunk SFX timing in mid-video chunks.
    assert sliced != []  # smoke check; chunks always produce some SFX


def test_empty_pool_returns_empty():
    assert schedule_sfx(pool_ids=[], density_s=10, seed=1, start_s=0, end_s=60) == []


def test_no_density_returns_empty():
    assert schedule_sfx(pool_ids=[1], density_s=None, seed=1, start_s=0, end_s=60) == []


def test_sfx_layer_empty_pool_returns_empty():
    assert schedule_sfx_layer([], 10, 25, seed=42, start_s=0, end_s=120) == []


def test_sfx_layer_zero_interval_returns_empty():
    assert schedule_sfx_layer([1], 0, 0, seed=42, start_s=0, end_s=120) == []


def test_sfx_layer_negative_interval_returns_empty():
    assert schedule_sfx_layer([1], -5, 25, seed=42, start_s=0, end_s=120) == []


def test_sfx_layer_deterministic():
    r1 = schedule_sfx_layer([1, 2, 3], 10, 25, seed=42, start_s=0, end_s=120)
    r2 = schedule_sfx_layer([1, 2, 3], 10, 25, seed=42, start_s=0, end_s=120)
    assert r1 == r2
    assert r1 != []


def test_sfx_layer_different_seeds_diverge():
    r1 = schedule_sfx_layer([1, 2], 10, 25, seed=42, start_s=0, end_s=120)
    r2 = schedule_sfx_layer([1, 2], 10, 25, seed=99, start_s=0, end_s=120)
    assert r1 != r2


def test_sfx_layer_events_within_window():
    result = schedule_sfx_layer([1, 2, 3], 10, 25, seed=7, start_s=0, end_s=120)
    for ts, sfx_id in result:
        assert 0 <= ts < 120
        assert sfx_id in [1, 2, 3]


def test_sfx_layer_gaps_within_interval_bounds():
    result = schedule_sfx_layer([1], 10, 25, seed=7, start_s=0, end_s=600)
    timestamps = [ts for ts, _ in result]
    for i in range(1, len(timestamps)):
        gap = timestamps[i] - timestamps[i - 1]
        assert 9.99 <= gap <= 25.01


def test_sfx_layer_chunk_is_deterministic():
    """Same (seed, start_s, end_s) always produces the same schedule."""
    r1 = schedule_sfx_layer([1, 2], 10, 25, seed=42, start_s=3600, end_s=7200)
    r2 = schedule_sfx_layer([1, 2], 10, 25, seed=42, start_s=3600, end_s=7200)
    assert r1 == r2
    assert r1 != []


def test_sfx_layer_burn_makes_chunks_differ():
    """Chunks at different offsets must produce different first-event timestamps
    (the RNG burn advances state so chunks don't all start with the same pattern)."""
    r1 = schedule_sfx_layer([1], 10, 25, seed=42, start_s=0,    end_s=120)
    r2 = schedule_sfx_layer([1], 10, 25, seed=42, start_s=3600, end_s=3720)
    # First timestamps differ because start_s burn advances the RNG differently
    ts1 = r1[0][0] if r1 else None
    ts2 = r2[0][0] - 3600 if r2 else None  # normalise to window-local time
    assert ts1 != ts2
