import scripts.scheduled_crawl_runner as runner


def test_require_phase_success_tolerates_boost_failure_in_lenient_mode(monkeypatch):
    monkeypatch.setattr(runner, "STRICT_MODE", False)
    phase = {
        "status": "failed",
        "scheduled_crawl": {"status": "success"},
        "meta_instagram_boost": {"status": "failed"},
    }
    runner._require_phase_success("crawl", phase)


def test_require_phase_success_raises_when_main_crawl_failed(monkeypatch):
    monkeypatch.setattr(runner, "STRICT_MODE", False)
    phase = {
        "status": "failed",
        "scheduled_crawl": {"status": "failed"},
        "meta_instagram_boost": {"status": "failed"},
    }
    try:
        runner._require_phase_success("crawl", phase)
        assert False, "expected RuntimeError"
    except RuntimeError:
        pass

