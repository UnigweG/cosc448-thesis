def test_first_last_uses_time_not_string_order(scripts):
    first_last = scripts("02b_repo_stats.py").first_last
    # W2023 team-21: the -07:00 string sorts first but is 3 h later than the Z commit
    log = ["1696203204 2023-10-01T16:33:24-07:00",
           "1696191706 2023-10-01T20:21:46Z",
           "1712640000 2024-04-09T05:20:00Z"]
    assert first_last(log) == ("2023-10-01T20:21:46Z", "2024-04-09T05:20:00Z")


def test_first_last_latest_with_positive_offset(scripts):
    first_last = scripts("02b_repo_stats.py").first_last
    # W2025 team-12: +05:30 sorts last as a string but is 10 h earlier
    log = ["1774814037 2026-03-30T01:23:57+05:30",
           "1774850866 2026-03-29T23:07:46-07:00"]
    assert first_last(log)[1] == "2026-03-29T23:07:46-07:00"
