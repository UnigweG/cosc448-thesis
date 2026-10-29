"""20/21: file exclusion reasons, token chunking and percentile ranks (no models needed)."""
import pandas as pd
import pytest


@pytest.fixture
def det(scripts):
    return scripts("20_file_detect.py")


@pytest.fixture
def agg(scripts):
    return scripts("21_aggregate.py")


class FakeTok:
    """One token per character; offsets are the character spans (enough to test the chunk bounds)."""

    def __call__(self, text, add_special_tokens=False, return_offsets_mapping=False):
        enc = {"input_ids": list(range(len(text)))}
        if return_offsets_mapping:
            enc["offset_mapping"] = [(i, i + 1) for i in range(len(text))]
        return enc


def reason(det, path, text, repo="r", dirs=("node_modules", "dist"), keep_build=(), vendored=None):
    return det.exclusion_reason(repo, path, text, set(dirs), set(keep_build), vendored or {})


def test_plain_source_file_is_included(det):
    assert reason(det, "src/app.py", "def f():\n    return 1\n") == ""


def test_sonar_directory_and_minified_are_excluded(det):
    assert reason(det, "node_modules/x/a.js", "var a = 1;\n").startswith("sonar_exclusion:dir=")
    assert reason(det, "static/a.min.js", "var a = 1;\n") == "sonar_exclusion:*.min.js"


def test_build_dir_is_kept_for_listed_repos(det):
    assert reason(det, "build/a.py", "x = 1\n", dirs=("build",)).startswith("sonar_exclusion")
    assert reason(det, "build/a.py", "x = 1\n", dirs=("build",), keep_build=("r",)) == ""


def test_vendored_packages_and_vendor_dirs(det):
    assert reason(det, "src/public/packages/ck/a.js", "var a = 1;\n", vendored={"r": "src/public/packages/**"}
                  ).startswith("vendored_packages")
    assert reason(det, "vendor/a.php", "<?php echo 1;\n").startswith("vendored_dir")


def test_generated_and_binary_and_empty_and_minified_data(det):
    assert reason(det, "a.d.ts", "declare const a: number;\n") == "generated_or_declaration_file"
    assert reason(det, "a.py", "x\0y\n") == "binary_nul_bytes"
    assert reason(det, "a.py", "# Auto-generated, do not edit\nx = 1\n") == "generated_marker_in_header"
    assert reason(det, "a.py", "\n\n   \n") == "empty"
    assert reason(det, "a.js", "a" * 500 + "\n").startswith("minified_or_data")


def test_chunks_cover_the_text_without_overlap_and_respect_the_limit(det):
    text = "".join(f"line {i:03d}\n" for i in range(60))  # 9 chars per line
    spans, ids = det.split_tokens(text, FakeTok(), 100)
    assert len(ids) == len(text)
    assert spans[0][0] == 0 and spans[-1][1] == len(text)
    for (_, j, _, _), (i2, _, _, _) in zip(spans, spans[1:]):
        assert j == i2
    assert all(j - i <= 100 for i, j, _, _ in spans)


def test_chunks_are_cut_at_line_ends_when_possible(det):
    text = "".join(f"line {i:03d}\n" for i in range(60))
    spans, _ = det.split_tokens(text, FakeTok(), 100)
    for _, j, _, ce in spans[:-1]:
        assert text[ce - 1] == "\n"


def test_short_tail_borrows_from_the_previous_chunk(det):
    text = "x" * 105  # no newline: exact cut at 100, tail of 5 < MIN_TAIL
    spans, _ = det.split_tokens(text, FakeTok(), 100)
    assert len(spans) == 2
    assert spans[-1][1] - spans[-1][0] == det.MIN_TAIL
    assert spans[0][1] == spans[1][0]


def test_single_short_text_is_one_chunk(det):
    spans, _ = det.split_tokens("x = 1\n", FakeTok(), 100)
    assert len(spans) == 1


def test_percentile_is_a_rank_from_0_to_100(agg):
    p = agg.percentile(pd.Series([3.0, 1.0, 2.0]))
    assert list(p) == [100.0, 0.0, 50.0]
    assert list(agg.percentile(pd.Series([5.0]))) == [0.0]


def test_scores_of_edited_or_dropped_files_are_not_aggregated(agg):
    files = pd.DataFrame({"year": 2024, "repo": "r", "path": ["a.py", "a.py", "b.py", "c.py"],
                          "content_hash": ["old", "new", "b1", "c1"], "bino_score": [1.0, 2.0, 3.0, 4.0]})
    inv = pd.DataFrame({"year": 2024, "repo": "r", "path": ["a.py", "b.py", "c.py"],
                        "content_hash": ["new", "b1", "c1"], "included": ["yes", "yes", "no"]})
    kept = agg.current_scores(files, inv)
    # a.py keeps only its current version; c.py is now excluded
    assert sorted(zip(kept.path, kept.content_hash)) == [("a.py", "new"), ("b.py", "b1")]


def test_manual_check_results_survive_regenerating_the_kit(agg):
    cols = ["year", "repo", "path", *agg.ANNOTATIONS]
    existing = pd.DataFrame([[2024, "r", "a.py", "63", "AI", "0.9", "ai", "checked by hand"]], columns=cols)
    kit = pd.DataFrame({"year": 2024, "repo": "r", "path": ["a.py", "b.py"], "kit_file": ["f1", "f2"],
                        **{c: ["", ""] for c in agg.ANNOTATIONS}})
    out = agg.keep_annotations(kit, existing).set_index("path")
    assert out.loc["a.py", "zerogpt_label"] == "AI" and out.loc["a.py", "notes"] == "checked by hand"
    assert out.loc["b.py", "notes"] == "" and list(out.kit_file) == ["f1", "f2"]
    assert agg.keep_annotations(kit, None) is kit
