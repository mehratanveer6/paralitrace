import pytest

from paralitrace import agent
from paralitrace.config import load_env_file


def test_env_file_parsing(tmp_path, monkeypatch):
    for k in ("A_KEY", "B_KEY", "C_KEY", "D_KEY"):
        monkeypatch.delenv(k, raising=False)
    monkeypatch.setenv("D_KEY", "from-shell")
    f = tmp_path / ".env"
    f.write_text('# comment\nA_KEY=abc123\nB_KEY=   # blank, skipped\nC_KEY="quoted"\nD_KEY=from-file\n', encoding="utf-8")
    load_env_file(str(f))
    import os
    assert os.environ["A_KEY"] == "abc123"
    assert "B_KEY" not in os.environ
    assert os.environ["C_KEY"] == "quoted"
    assert os.environ["D_KEY"] == "from-shell"   # shell wins over file


@pytest.fixture
def clean_env(monkeypatch):
    for k in ("PT_MODEL", "GEMINI_API_KEY", "ANTHROPIC_API_KEY", "OLLAMA_MODEL", "AWS_ACCESS_KEY_ID", "AWS_PROFILE", "GEMINI_MODEL"):
        monkeypatch.delenv(k, raising=False)
    agent._working.clear()
    return monkeypatch


def test_no_model_gives_actionable_error(clean_env):
    with pytest.raises(agent.NoModelConfigured, match="aistudio.google.com"):
        agent.provider()


def test_gemini_preferred_with_fallback_models(clean_env):
    clean_env.setenv("GEMINI_API_KEY", "k")
    assert agent.provider() == "gemini"
    assert [m.config["model_id"] for m in agent.candidates()] == list(agent.GEMINI_MODELS)
    clean_env.setenv("GEMINI_MODEL", "my-model")
    assert [m.config["model_id"] for m in agent.candidates()] == ["my-model"]


def test_ask_falls_back_when_a_model_is_unavailable(clean_env):
    calls = []

    class FakeAgent:
        def __init__(self, model, **kw):
            self.model = model

        def __call__(self, q):
            calls.append(self.model)
            if self.model == "first":
                raise RuntimeError("404 models/first is not found")
            return "answer from " + self.model

    clean_env.setattr(agent, "Agent", FakeAgent)
    clean_env.setattr(agent, "candidates", lambda: ["first", "second"])
    assert agent.ask("hi") == "answer from second"
    assert agent.ask("again") == "answer from second"   # remembers the working model
    assert calls == ["first", "second", "second"]


def test_ask_does_not_hide_real_errors(clean_env):
    class Boom:
        def __init__(self, model, **kw):
            pass

        def __call__(self, q):
            raise ValueError("bad tool schema")

    clean_env.setattr(agent, "Agent", Boom)
    clean_env.setattr(agent, "candidates", lambda: ["a", "b"])
    with pytest.raises(ValueError):
        agent.ask("hi")


def test_report_fills_numbers_and_never_invents_missing_ones():
    from paralitrace.report import build
    latest = {"meta": {"mode": "replay", "data_label": "Replay of 4 Nov 2025: NASA FIRMS archive fires + ERA5 winds"},
              "plan": {"exposure_avoided_pct_of_preventable": 61.2, "budget_fires": 40,
                       "naive_biggest_fires_pct_of_preventable": 30.1},
              "counterfactual": {"cities": [{"name": "Delhi", "reduction_pct": 34.6}, {"name": "Karnal", "reduction_pct": 20.0}]}}
    bt = {"season": "Oct-Nov 2025", "cities": [1, 2],
          "summary": {"spikes_caught": 20, "spike_days": 30, "hit_rate_pct": 67, "baseline_hit_rate_pct": 50,
                      "baseline_label": "repeating yesterday's PM2.5", "onset_days": 8, "onsets_caught": 5,
                      "false_alarm_pct": 25, "median_correlation": 0.55},
          "heldout": {"train": "Oct 2025", "test": "Nov 2025", "spike_days": 90, "onset_days": 40, "test_city_days": 400,
                      "methods": [
                          {"key": "persistence", "label": "Repeat", "caught": 50, "false_alarm_pct": 40, "onsets_caught": 0, "mae": 60.0},
                          {"key": "smoke_only", "label": "S", "caught": 45, "false_alarm_pct": 50, "onsets_caught": 18, "mae": None},
                          {"key": "calibrated_no_smoke", "label": "C0", "caught": 52, "false_alarm_pct": 38, "onsets_caught": 2, "mae": 55.0},
                          {"key": "calibrated", "label": "C", "caught": 61, "false_alarm_pct": 33, "onsets_caught": 12, "mae": 48.5}]}}
    text = build(latest, bt)
    for frag in ("61.2%", "30.1%", "40 fire locations", "4 Nov 2025", "Delhi 35% less smoke", "61 of 90",
                 "48.5", "Strands Agents SDK", "AWS open source:", "AWS services:"):
        assert frag in text, frag
    assert "[[" not in text and "demo data" not in text and "[X]" not in text
    empty = build(None, None)
    assert "Not run yet" in empty and "Run the pipeline" in empty
    assert "demo data" in build({**latest, "meta": {"mode": "synthetic"}}, None)


def test_demo_export_and_examples_match_the_ui(tmp_path, monkeypatch):
    import json, os, re
    from paralitrace import export_demo
    tsx = open(os.path.join(os.path.dirname(__file__), "..", "frontend", "src", "components", "AskPane.tsx"), encoding="utf-8").read()
    ui = re.findall(r"^  '(.+)',$", tsx[tsx.index("const EXAMPLES"):tsx.index("];")], re.M)
    assert ui == export_demo.EXAMPLES

    out = tmp_path / "output"; out.mkdir()
    (out / "latest.json").write_text('{"meta": {}}'); (out / "backtest.json").write_text("{}")
    monkeypatch.setattr(export_demo, "OUTPUT_DIR", str(out))
    monkeypatch.setattr(agent, "ask_with_trace", lambda q: ("answer to " + q, [{"name": "run_info", "input": {}}]))
    demo = tmp_path / "demo"
    files = export_demo.export(out_dir=str(demo))
    assert files == ["latest.json", "backtest.json", "answers.json"]
    rec = json.loads((demo / "answers.json").read_text(encoding="utf-8"))
    assert [r["question"] for r in rec] == export_demo.EXAMPLES and rec[0]["tools"][0]["name"] == "run_info"
