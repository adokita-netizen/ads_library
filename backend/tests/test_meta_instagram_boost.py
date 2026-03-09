from scripts.run_daily_meta_instagram_boost import _select_priority_queries


def test_select_priority_queries_prefers_learned_success():
    learning_data = {
        "platforms": {
            "instagram": {
                "glp-1": {
                    "医療ダイエット": {"attempts": 5, "success": 3},
                    "美容": {"attempts": 5, "success": 0},
                }
            },
            "facebook": {
                "aga": {
                    "AGA治療": {"attempts": 3, "success": 2},
                }
            },
        }
    }
    queries = _select_priority_queries(learning_data, limit=6)
    assert queries[0] in {"glp-1", "aga"}
    assert "GLP-1" in queries
    assert "AGA治療" in queries

