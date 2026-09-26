from __future__ import annotations

import json
from pathlib import Path

from nba_lab.data_bundle import (
    select_replay_games,
    sync_season_bundle,
    write_json_artifact,
)
from nba_lab.domain import Game


def _schedule_payload():
    return {
        "SeasonGames": [
            {
                "gameId": "0022500001",
                "gameStatus": 3,
                "gameDateEst": "2025-10-21",
                "homeTeam_teamTricode": "BOS",
                "awayTeam_teamTricode": "NYK",
                "homeTeam_score": 110,
                "awayTeam_score": 109,
            },
            {
                "gameId": "0022500002",
                "gameStatus": 3,
                "gameDateEst": "2025-10-22",
                "homeTeam_teamTricode": "DEN",
                "awayTeam_teamTricode": "OKC",
                "homeTeam_score": 121,
                "awayTeam_score": 115,
            },
            {
                "gameId": "0022500003",
                "gameStatus": 3,
                "gameDateEst": "2025-10-23",
                "homeTeam_teamTricode": "NYK",
                "awayTeam_teamTricode": "BOS",
                "homeTeam_score": 99,
                "awayTeam_score": 101,
            },
            {
                "gameId": "0022500004",
                "gameStatus": 1,
                "gameDateEst": "2025-10-24",
                "homeTeam_teamTricode": "BOS",
                "awayTeam_teamTricode": "DEN",
                "homeTeam_score": 0,
                "awayTeam_score": 0,
            },
        ]
    }


def test_select_replay_games_prefers_close_games_and_team_filter():
    games = [
        Game("a", __import__("datetime").date(2025, 1, 1), "BOS", "NYK", 100, 99),
        Game("b", __import__("datetime").date(2025, 1, 3), "DEN", "OKC", 110, 109),
        Game("c", __import__("datetime").date(2025, 1, 2), "BOS", "DEN", 108, 106),
        Game("d", __import__("datetime").date(2025, 1, 4), "BOS", "OKC", None, None),
    ]
    selected = select_replay_games(games, count=2)
    # Same one-point margin: newer game first.
    assert [game.game_id for game in selected] == ["b", "a"]

    bos = select_replay_games(games, count=5, teams={"bos"})
    assert [game.game_id for game in bos] == ["a", "c"]


def test_write_json_artifact_is_stable_and_atomic(tmp_path):
    target = tmp_path / "nested" / "payload.json"
    first = write_json_artifact(target, {"b": 2, "a": 1})
    second = write_json_artifact(target, {"a": 1, "b": 2})

    assert first["sha256"] == second["sha256"]
    assert first["bytes"] == second["bytes"]
    assert json.loads(target.read_text()) == {"a": 1, "b": 2}
    assert not target.with_suffix(".json.tmp").exists()


def test_bundle_sync_records_partial_replay_failure_and_manifest(tmp_path):
    calls = {"replays": [], "impact": None}

    def schedule_fetcher(season):
        assert season == "2025-26"
        return _schedule_payload()

    def player_logs_fetcher(season):
        assert season == "2025-26"
        return {"PlayerGameLogs": [{"PLAYER_ID": 1, "GAME_ID": "0022500001"}]}

    def replay_fetcher(game_id):
        calls["replays"].append(game_id)
        if game_id == "0022500003":
            raise RuntimeError("temporary replay failure")
        return {
            "PlayByPlay": [
                {
                    "gameId": game_id,
                    "actionNumber": 1,
                    "period": 1,
                    "clock": "PT12M00.00S",
                }
            ]
        }

    def impact_builder(**kwargs):
        calls["impact"] = kwargs
        payload = {
            "source": "fake",
            "players": [],
            "stints": [{"game_id": "0022500001"}],
            "qa": {"games_loaded": 1},
        }
        Path(kwargs["output_path"]).write_text(json.dumps(payload))
        return payload

    manifest = sync_season_bundle(
        "2025-26",
        output_dir=tmp_path,
        replay_count=2,
        replay_teams={"BOS"},
        impact_games=12,
        impact_source="file",
        impact_teams={"BOS", "NYK"},
        schedule_fetcher=schedule_fetcher,
        player_logs_fetcher=player_logs_fetcher,
        replay_fetcher=replay_fetcher,
        impact_builder=impact_builder,
    )

    assert (tmp_path / "scheduleLeagueV2.json").exists()
    assert (tmp_path / "playerGameLogs.json").exists()
    assert (tmp_path / "nba_lab_bundle_manifest.json").exists()
    assert manifest["season"] == "2025-26"
    assert manifest["schedule"]["games"] == 4
    assert manifest["schedule"]["final_games"] == 3

    # BOS-filtered replay selection chooses the 1-point and 2-point games.
    assert calls["replays"] == ["0022500001", "0022500003"]
    statuses = {row["game_id"]: row["status"] for row in manifest["replays"]}
    assert statuses == {
        "0022500001": "ok",
        "0022500003": "error",
    }
    assert "temporary replay failure" in next(
        row["error"] for row in manifest["replays"] if row["status"] == "error"
    )

    assert manifest["impact"]["status"] == "ok"
    assert manifest["impact"]["stints"] == 1
    assert calls["impact"]["max_games"] == 12
    assert calls["impact"]["source"] == "file"
    assert calls["impact"]["teams"] == {"BOS", "NYK"}

    persisted = json.loads((tmp_path / "nba_lab_bundle_manifest.json").read_text())
    assert persisted["selection"]["replay_teams"] == ["BOS"]
    assert persisted["selection"]["impact_teams"] == ["BOS", "NYK"]
