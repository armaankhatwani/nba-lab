from fastapi.testclient import TestClient

from nba_lab.web import GAMES, app

client = TestClient(app)


def test_status_and_home_load():
    assert client.get('/').status_code == 200
    status = client.get('/api/status').json()
    assert status['games'] > 100
    assert status['teams'] == 30


def test_compare_api_returns_paired_delta():
    r = client.post('/api/compare', json={
        'as_of': '2026-01-15', 'trials': 200, 'seed': 7, 'team': 'NYK', 'elo_delta': 100
    })
    assert r.status_code == 200
    data = r.json()
    delta = next(x for x in data['deltas'] if x['team'] == 'NYK')
    assert delta['expected_wins_delta'] > 0
    assert data['intervention']['label'] == 'research strength adjustment'


def test_recent_games_and_historical_flip_api():
    games = client.get('/api/games?before=2026-01-15&team=NYK&limit=5').json()
    assert games and all('NYK' in {g['home_team'], g['away_team']} for g in games)
    r = client.post('/api/flip-game', json={
        'as_of': '2026-01-15', 'trials': 200, 'seed': 7, 'game_id': games[0]['game_id']
    })
    assert r.status_code == 200
    data = r.json()
    assert data['intervention']['kind'] == 'flip_game'
    assert data['intervention']['original_winner'] != data['intervention']['flipped_winner']
    assert 'award_ripple' in data


def test_timeline_and_diagnostics_endpoints():
    timeline = client.get('/api/timeline/NYK')
    assert timeline.status_code == 200
    payload = timeline.json()
    assert payload['points']
    assert payload['summary']['games'] == len(payload['points'])

    diagnostics = client.get('/api/diagnostics')
    assert diagnostics.status_code == 200
    data = diagnostics.json()
    assert data['metrics']['games'] > 0
    assert data['calibration']
    assert data['model']['name'] == 'Frozen Elo baseline'


def test_matchup_api_simulates_series():
    r = client.post('/api/matchup', json={
        'as_of': '2026-01-15', 'trials': 200, 'seed': 7,
        'team_a': 'NYK', 'team_b': 'BOS', 'best_of': 7
    })
    assert r.status_code == 200
    data = r.json()
    assert abs(data['team_a_series_probability'] + data['team_b_series_probability'] - 1) < 1e-9
    assert 4 <= data['expected_games'] <= 7


def test_awards_race_and_history_api():
    race = client.get('/api/awards/race?as_of=2026-01-15&limit=5')
    assert race.status_code == 200
    data = race.json()
    assert data['award'] == 'MVP'
    assert len(data['candidates']) <= 5
    if data['candidates']:
        assert abs(sum(c['race_share'] for c in client.get('/api/awards/race?as_of=2026-01-15&limit=25').json()['candidates']) - 1) < 1e-9

    history = client.get('/api/awards/history?step_days=14&limit=4')
    assert history.status_code == 200
    assert history.json()['snapshots']


def test_awards_simulation_api_returns_distribution():
    r = client.post('/api/awards/simulate', json={
        'as_of': '2026-01-15', 'trials': 100, 'seed': 5
    })
    assert r.status_code == 200
    data = r.json()
    assert data['candidates']
    assert abs(sum(c['leader_probability'] for c in data['candidates']) - 1) < 1e-9


def test_player_impact_and_regularization_path_api():
    impact = client.get('/api/impact?alpha=1000&limit=20')
    assert impact.status_code == 200
    data = impact.json()
    assert data['players']
    player_id = data['players'][0]['player_id']
    path = client.get(f'/api/impact/{player_id}/path')
    assert path.status_code == 200
    points = path.json()['points']
    assert [p['alpha'] for p in points] == [100.0, 300.0, 1000.0, 3000.0]


def test_lineup_players_and_compare_api():
    players = client.get('/api/lineup/players?alpha=1000').json()['players']
    assert len(players) >= 10
    a = [p['player_id'] for p in players[:5]]
    b = [p['player_id'] for p in players[5:10]]
    if set(a) & set(b):
        raise AssertionError('test fixture lineups overlap')
    r = client.post('/api/lineup/compare', json={
        'lineup_a': a, 'lineup_b': b, 'alpha': 1000, 'prior_possessions': 300
    })
    assert r.status_code == 200
    data = r.json()
    assert len(data['lineup_a']['player_meta']) == 5
    assert len(data['lineup_b']['player_meta']) == 5
    assert isinstance(data['neutral_margin_per_100'], float)


def test_leverage_api_ranks_upcoming_games():
    r = client.get('/api/leverage?as_of=2026-01-15&trials=100&limit=3')
    assert r.status_code == 200
    data = r.json()
    assert len(data['games']) == 3
    assert data['games'][0]['title_distribution_shift'] >= data['games'][-1]['title_distribution_shift']


def test_game_replay_endpoints_and_intervention():
    listing = client.get('/api/replay/games')
    assert listing.status_code == 200
    games = listing.json()['games']
    assert games
    game_id = games[0]['game_id']

    replay = client.get(f'/api/replay/{game_id}')
    assert replay.status_code == 200
    payload = replay.json()
    assert payload['events']
    event = payload['events'][len(payload['events']) // 2]

    result = client.post('/api/replay/simulate', json={
        'game_id': game_id,
        'action_number': event['action_number'],
        'trials': 500,
        'seed': 7,
        'home_score_delta': 3,
        'away_score_delta': 0,
    })
    assert result.status_code == 200
    data = result.json()
    assert data['home_win_probability_delta'] >= 0
    assert abs(data['expected_final_margin_delta'] - 3) < 1e-9
    assert 'season_ripple' in data
    assert data['season_ripple']['teams']


def test_player_absence_scenario_api():
    players = client.get('/api/impact?alpha=1000&limit=50').json()['players']
    player = next(row for row in players if row['impact_per_100'] > 0)
    r = client.post('/api/scenario/player-absence', json={
        'as_of': '2026-01-15',
        'trials': 200,
        'seed': 12,
        'alpha': 1000,
        'absences': [{
            'player_id': player['player_id'],
            'games_missed': 8,
            'minutes_per_game': 36,
            'replacement_impact_per_100': 0
        }]
    })
    assert r.status_code == 200
    data = r.json()
    effect = data['player_absences'][0]
    team = effect['team']
    delta = next(row for row in data['deltas'] if row['team'] == team)
    assert effect['affected_game_ids']
    assert effect['elo_delta_per_game'] < 0
    assert delta['expected_wins_delta'] < 0


def test_scenario_api_composes_historical_flip_and_absence():
    games = client.get('/api/games?before=2026-01-15&limit=5').json()
    players = client.get('/api/impact?alpha=1000&limit=50').json()['players']
    player = next(row for row in players if row['impact_per_100'] > 0)
    r = client.post('/api/scenario/player-absence', json={
        'as_of': '2026-01-15',
        'trials': 150,
        'seed': 13,
        'alpha': 1000,
        'flipped_game_ids': [games[0]['game_id']],
        'absences': [{
            'player_id': player['player_id'],
            'games_missed': 5,
            'minutes_per_game': 36,
            'replacement_impact_per_100': 0
        }]
    })
    assert r.status_code == 200
    data = r.json()
    assert len(data['historical_flips']) == 1
    assert data['historical_flips'][0]['original_winner'] != data['historical_flips'][0]['flipped_winner']
    assert 'award_ripple' in data


def test_trade_only_scenario_api():
    players = client.get('/api/impact?alpha=1000&limit=100').json()['players']
    a = players[0]
    b = next(row for row in reversed(players) if row['team'] != a['team'])
    r = client.post('/api/scenario/player-absence', json={
        'as_of': '2026-01-15',
        'trials': 150,
        'seed': 15,
        'alpha': 1000,
        'trades': [{
            'player_a_id': a['player_id'],
            'player_b_id': b['player_id'],
            'minutes_per_game': 34
        }]
    })
    assert r.status_code == 200
    data = r.json()
    assert len(data['trades']) == 1
    effect = data['trades'][0]
    assert effect['team_a'] != effect['team_b']
    assert effect['team_a_elo_delta_per_game'] * effect['team_b_elo_delta_per_game'] <= 0


def test_scenario_awards_propagates_shared_star_absence():
    r = client.post('/api/scenario/awards?award_trials=150', json={
        'as_of': '2026-01-15',
        'trials': 200,
        'seed': 19,
        'alpha': 1000,
        'absences': [{
            'player_id': '1628369',
            'games_missed': 12,
            'minutes_per_game': 36,
            'replacement_impact_per_100': 0
        }]
    })
    assert r.status_code == 200
    data = r.json()
    row = next(delta for delta in data['deltas'] if delta['player_id'] == '1628369')
    assert row['baseline_team'] == 'BOS'
    assert row['altered_team'] == 'BOS'
    assert row['leader_probability_delta'] <= 0


def test_scenario_awards_tracks_traded_candidate_team():
    r = client.post('/api/scenario/awards?award_trials=120', json={
        'as_of': '2026-01-15',
        'trials': 200,
        'seed': 23,
        'alpha': 1000,
        'trades': [{
            'player_a_id': '203999',
            'player_b_id': '1628369',
            'minutes_per_game': 34
        }]
    })
    assert r.status_code == 200
    data = r.json()
    jokic = next(row for row in data['deltas'] if row['player_id'] == '203999')
    tatum = next(row for row in data['deltas'] if row['player_id'] == '1628369')
    assert jokic['baseline_team'] == 'DEN' and jokic['altered_team'] == 'BOS'
    assert tatum['baseline_team'] == 'BOS' and tatum['altered_team'] == 'DEN'


def test_scenario_sensitivity_orders_positive_player_absence_worlds():
    r = client.post('/api/scenario/sensitivity?sensitivity_trials=180', json={
        'as_of': '2026-01-15',
        'trials': 200,
        'seed': 31,
        'alpha': 1000,
        'absences': [{
            'player_id': '1628369',
            'games_missed': 10,
            'minutes_per_game': 36,
            'replacement_impact_per_100': 0
        }]
    })
    assert r.status_code == 200
    data = r.json()
    lower = next(row for row in data['impact_lower']['teams'] if row['team'] == 'BOS')
    point = next(row for row in data['point']['teams'] if row['team'] == 'BOS')
    upper = next(row for row in data['impact_upper']['teams'] if row['team'] == 'BOS')
    # Higher assumed Tatum impact means a stronger absence penalty.
    assert upper['expected_wins'] <= point['expected_wins'] <= lower['expected_wins']


def test_scenario_sensitivity_preserves_historical_branch_across_worlds():
    game = client.get('/api/games?before=2026-01-15&limit=1').json()[0]
    r = client.post('/api/scenario/sensitivity?sensitivity_trials=120', json={
        'as_of': '2026-01-15',
        'trials': 200,
        'seed': 32,
        'alpha': 1000,
        'flipped_game_ids': [game['game_id']]
    })
    assert r.status_code == 200
    data = r.json()
    # With no player-impact intervention, lower/point/upper are identical worlds.
    assert data['impact_lower']['teams'] == data['point']['teams'] == data['impact_upper']['teams']


def test_scenario_reports_affected_schedule_probability_shifts():
    r = client.post('/api/scenario/player-absence', json={
        'as_of': '2026-01-15',
        'trials': 120,
        'seed': 41,
        'alpha': 1000,
        'absences': [{
            'player_id': '1628369',
            'games_missed': 4,
            'minutes_per_game': 36,
            'replacement_impact_per_100': 0
        }]
    })
    assert r.status_code == 200
    data = r.json()
    effect = data['player_absences'][0]
    affected_ids = {row['game_id'] for row in data['affected_games']}
    assert affected_ids == set(effect['affected_game_ids'])
    assert 1 <= len(affected_ids) <= effect['games_missed']
    assert all('home_win_probability_delta' in row for row in data['affected_games'])
    assert any(abs(row['home_win_probability_delta']) > 0 for row in data['affected_games'])


def test_home_page_contains_all_live_lab_views():
    html = client.get('/').text
    for view_id in (
        'view-season',
        'view-scenario',
        'view-matchup',
        'view-timeline',
        'view-model',
        'view-awards',
        'view-impact',
        'view-lineup',
        'view-leverage',
        'view-game',
    ):
        assert f'id="{view_id}"' in html

    for element_id in (
        'matchup-a',
        'matchup-b',
        'matchup-date',
        'matchup-bestof',
        'matchup-trials',
        'matchup-run',
        'matchup-result',
    ):
        assert f'id="{element_id}"' in html


def test_scenario_matchup_uses_exact_affected_game_adjustment():
    scenario = client.post('/api/scenario/player-absence', json={
        'as_of': '2026-01-15',
        'trials': 150,
        'seed': 61,
        'alpha': 1000,
        'absences': [{
            'player_id': '1628369',
            'games_missed': 4,
            'minutes_per_game': 36,
            'replacement_impact_per_100': 0
        }]
    }).json()
    game = scenario['affected_games'][0]
    r = client.post('/api/scenario/matchup', json={
        'as_of': '2026-01-15',
        'trials': 500,
        'seed': 61,
        'alpha': 1000,
        'game_id': game['game_id'],
        'absences': [{
            'player_id': '1628369',
            'games_missed': 4,
            'minutes_per_game': 36,
            'replacement_impact_per_100': 0
        }]
    })
    assert r.status_code == 200
    data = r.json()
    assert 'BOS' in data['rating_adjustments']
    if data['game']['home_team'] == 'BOS':
        assert data['scenario']['team_a_rating'] < data['baseline']['team_a_rating']
    else:
        assert data['scenario']['team_b_rating'] < data['baseline']['team_b_rating']



def test_scenario_sensitivity_reports_direction_stability_summary():
    r = client.post('/api/scenario/sensitivity?sensitivity_trials=160', json={
        'as_of': '2026-01-15',
        'trials': 160,
        'seed': 81,
        'alpha': 1000,
        'absences': [{
            'player_id': '1628369',
            'games_missed': 3,
            'minutes_per_game': 36,
            'replacement_impact_per_100': 0
        }]
    })
    assert r.status_code == 200
    data = r.json()
    bos = next(row for row in data['team_sensitivity'] if row['team'] == 'BOS')
    assert len(bos['expected_wins_deltas']) == 3
    assert bos['expected_wins_range'][0] <= bos['expected_wins_range'][1]
    assert isinstance(bos['expected_wins_direction_stable'], bool)
    assert isinstance(bos['championship_direction_stable'], bool)


def test_impact_api_supports_historical_cutoff():
    full = client.get('/api/impact?alpha=1000&limit=500')
    assert full.status_code == 200
    historical = client.get('/api/impact?alpha=1000&limit=500&as_of=2025-12-01')
    assert historical.status_code == 200
    full_data = full.json()
    hist_data = historical.json()
    assert hist_data['as_of'] == '2025-12-01'
    assert hist_data['stints'] < full_data['stints']
    assert hist_data['games'] < full_data['games']


def test_impact_path_respects_historical_cutoff():
    r = client.get('/api/impact/1628369/path?as_of=2025-12-01')
    assert r.status_code == 200
    data = r.json()
    assert data['as_of'] == '2025-12-01'
    assert data['points']


def test_lineup_players_support_historical_cutoff():
    full = client.get('/api/lineup/players?alpha=1000')
    historical = client.get('/api/lineup/players?alpha=1000&as_of=2025-12-01')
    assert full.status_code == 200
    assert historical.status_code == 200
    assert historical.json()['as_of'] == '2025-12-01'
    assert historical.json()['players']


def test_lineup_compare_uses_historical_impact_slice():
    pool = client.get('/api/lineup/players?alpha=1000&as_of=2025-12-01').json()['players']
    ids = [row['player_id'] for row in pool[:10]]
    assert len(ids) == 10
    r = client.post('/api/lineup/compare', json={
        'lineup_a': ids[:5],
        'lineup_b': ids[5:10],
        'alpha': 1000,
        'prior_possessions': 300,
        'as_of': '2025-12-01'
    })
    assert r.status_code == 200
    assert r.json()['as_of'] == '2025-12-01'


def test_scenario_leverage_compares_rankings_to_baseline():
    r = client.post('/api/scenario/leverage?leverage_trials=120&limit=5', json={
        'as_of': '2026-01-15',
        'trials': 200,
        'seed': 91,
        'alpha': 1000,
        'absences': [{
            'player_id': '1628369',
            'games_missed': 3,
            'minutes_per_game': 36,
            'replacement_impact_per_100': 0
        }]
    })
    assert r.status_code == 200
    data = r.json()
    assert len(data['rows']) == 5
    assert {row['scenario_rank'] for row in data['rows']} == {1, 2, 3, 4, 5}
    assert {row['baseline_rank'] for row in data['rows']} == {1, 2, 3, 4, 5}
    assert all('rank_movement' in row for row in data['rows'])


def test_scenario_leverage_requires_an_intervention():
    r = client.post('/api/scenario/leverage?leverage_trials=100&limit=3', json={
        'as_of': '2026-01-15',
        'trials': 100,
        'seed': 92,
        'alpha': 1000
    })
    assert r.status_code == 422


def test_lineup_optimizer_api_returns_ranked_team_fives():
    r = client.get('/api/lineup/optimize?team=BOS&alpha=1000&prior_possessions=300&top_k=5')
    assert r.status_code == 200
    data = r.json()
    assert data['team'] == 'BOS'
    assert data['candidate_players'] >= 5
    assert 1 <= len(data['lineups']) <= 5
    scores = [row['blended_net_rating'] for row in data['lineups']]
    assert scores == sorted(scores, reverse=True)
    assert all(len(row['players']) == 5 for row in data['lineups'])


def test_lineup_optimizer_supports_historical_cutoff():
    r = client.get('/api/lineup/optimize?team=BOS&alpha=1000&as_of=2025-12-01&top_k=3')
    assert r.status_code == 200
    data = r.json()
    assert data['as_of'] == '2025-12-01'
    assert data['lineups']


def _first_future_game(as_of="2026-01-15"):
    rows = client.get(f'/api/upcoming-games?as_of={as_of}&limit=1').json()
    assert rows
    return rows[0]


def test_upcoming_games_are_point_in_time_schedule_only():
    rows = client.get('/api/upcoming-games?as_of=2026-01-15&limit=5')
    assert rows.status_code == 200
    data = rows.json()
    assert len(data) == 5
    assert all(row['date'] >= '2026-01-15' for row in data)
    assert all({'game_id','date','home_team','away_team'} <= set(row) for row in data)


def test_future_result_only_scenario_is_valid():
    game = _first_future_game()
    r = client.post('/api/scenario/run', json={
        'as_of': '2026-01-15',
        'trials': 160,
        'seed': 101,
        'alpha': 1000,
        'future_results': [{
            'game_id': game['game_id'],
            'winner': game['away_team']
        }]
    })
    assert r.status_code == 200
    data = r.json()
    assert len(data['future_results']) == 1
    assert data['future_results'][0]['forced_winner'] == game['away_team']
    assert any(abs(row['expected_wins_delta']) > 0 for row in data['deltas'])


def test_scenario_sensitivity_preserves_forced_future_result():
    game = _first_future_game()
    r = client.post('/api/scenario/sensitivity?sensitivity_trials=120', json={
        'as_of': '2026-01-15',
        'trials': 120,
        'seed': 102,
        'alpha': 1000,
        'future_results': [{
            'game_id': game['game_id'],
            'winner': game['home_team']
        }],
        'absences': [{
            'player_id': '1628369',
            'games_missed': 2,
            'minutes_per_game': 36,
            'replacement_impact_per_100': 0
        }]
    })
    assert r.status_code == 200
    data = r.json()
    assert data['point']['trials'] == 120
    assert data['impact_lower']['trials'] == 120
    assert data['impact_upper']['trials'] == 120


def test_scenario_leverage_excludes_fixed_future_game():
    game = _first_future_game()
    r = client.post('/api/scenario/leverage?leverage_trials=100&limit=5', json={
        'as_of': '2026-01-15',
        'trials': 100,
        'seed': 103,
        'alpha': 1000,
        'future_results': [{
            'game_id': game['game_id'],
            'winner': game['home_team']
        }]
    })
    assert r.status_code == 200
    data = r.json()
    assert data['rows']
    assert all(row['game_id'] != game['game_id'] for row in data['rows'])


def test_scenario_matchup_flags_when_game_is_already_forced():
    game = _first_future_game()
    r = client.post('/api/scenario/matchup', json={
        'as_of': '2026-01-15',
        'trials': 120,
        'seed': 104,
        'alpha': 1000,
        'game_id': game['game_id'],
        'future_results': [{
            'game_id': game['game_id'],
            'winner': game['away_team']
        }]
    })
    assert r.status_code == 200
    data = r.json()
    assert data['forced_winner'] == game['away_team']
    assert 0 <= data['scenario']['team_a_series_probability'] <= 1


def test_model_elo_surface_keeps_selection_and_holdout_separate():
    r = client.get('/api/model/elo-surface')
    assert r.status_code == 200
    data = r.json()
    assert data['train_games'] > 0
    assert data['validation_games'] > 0
    assert len(data['candidates']) == 36
    assert data['baseline']['k'] == 20
    assert data['baseline']['home_advantage'] == 65
    best_train = min(row['train']['brier'] for row in data['candidates'])
    assert abs(data['selected_on_train']['train']['brier'] - best_train) < 1e-12


def test_scenario_lineups_move_traded_players_between_rosters():
    r = client.post('/api/scenario/lineups?top_k=3', json={
        'as_of': '2026-01-15',
        'trials': 200,
        'seed': 31,
        'alpha': 1000,
        'trades': [{
            'player_a_id': '203999',
            'player_b_id': '1628369',
            'minutes_per_game': 34
        }]
    })
    assert r.status_code == 200
    data = r.json()
    teams = {row['team']: row for row in data['teams']}
    assert {'BOS', 'DEN'} <= set(teams)
    assert '203999' in teams['BOS']['scenario_roster']
    assert '1628369' not in teams['BOS']['scenario_roster']
    assert '1628369' in teams['DEN']['scenario_roster']
    assert '203999' not in teams['DEN']['scenario_roster']


def test_scenario_lineups_remove_absent_player_from_available_fives():
    r = client.post('/api/scenario/lineups?top_k=5', json={
        'as_of': '2026-01-15',
        'trials': 200,
        'seed': 32,
        'alpha': 1000,
        'absences': [{
            'player_id': '1628369',
            'games_missed': 3,
            'minutes_per_game': 36,
            'replacement_impact_per_100': 0
        }]
    })
    assert r.status_code == 200
    data = r.json()
    bos = next(row for row in data['teams'] if row['team'] == 'BOS')
    assert '1628369' not in bos['scenario_roster']
    assert all(
        '1628369' not in lineup['players']
        for lineup in bos['scenario_lineups']
    )


def test_trade_scenario_exposes_persistent_team_strength():
    players = client.get('/api/impact?alpha=1000&limit=100').json()['players']
    a = players[0]
    b = next(row for row in reversed(players) if row['team'] != a['team'])
    r = client.post('/api/scenario/run', json={
        'as_of': '2026-01-15',
        'trials': 120,
        'seed': 92,
        'alpha': 1000,
        'trades': [{
            'player_a_id': a['player_id'],
            'player_b_id': b['player_id'],
            'minutes_per_game': 34
        }]
    })
    assert r.status_code == 200
    data = r.json()
    adjustments = data['team_rating_adjustments']
    assert adjustments[a['team']] != 0
    assert adjustments[b['team']] != 0
    assert adjustments[a['team']] * adjustments[b['team']] <= 0
    assert data['affected_games']


def test_scenario_world_returns_complete_playoff_path():
    r = client.post('/api/scenario/world?world_seed=123', json={
        'as_of': '2026-01-15',
        'trials': 100,
        'seed': 2026,
        'alpha': 1000,
        'future_results': []
    })
    assert r.status_code == 200
    data = r.json()
    assert data['seed'] == 123
    assert len(data['standings']) == 30
    assert len([row for row in data['standings'] if row['playoff_seed'] is not None]) == 16
    assert len(data['play_in_games']) == 6
    assert len(data['series']) == 15
    assert data['champion']


def test_scenario_world_honors_forced_result():
    # Use the same in-memory schedule as the API fixture.
    target = next(
        game for game in GAMES
        if game.game_date.isoformat() >= '2026-01-15'
    )
    r = client.post('/api/scenario/world?world_seed=124', json={
        'as_of': '2026-01-15',
        'trials': 100,
        'seed': 2026,
        'alpha': 1000,
        'future_results': [{
            'game_id': target.game_id,
            'winner': target.away_team
        }]
    })
    assert r.status_code == 200
    data = r.json()
    game = next(row for row in data['remaining_games'] if row['game_id'] == target.game_id)
    assert game['forced'] is True
    assert game['winner'] == target.away_team


def test_status_exposes_data_bundle_contract():
    r = client.get('/api/status')
    assert r.status_code == 200
    data = r.json()
    assert 'bundle' in data
    assert data['bundle']['kind'] in {
        'none',
        'bundle_manifest',
        'invalid_manifest',
    }


def test_model_family_endpoint_exposes_holdout_gate():
    r = client.get('/api/model/families')
    assert r.status_code == 200
    data = r.json()
    assert data['baseline']['family'] == 'deployed_elo'
    assert data['tuned_plain']['family'] == 'tuned_plain_elo'
    assert data['score_aware']['family'] == 'score_aware_elo'
    assert data['validation_games'] > 0
    assert data['score_aware_vs_baseline']['games'] == data['validation_games']


def test_scenario_game_lineups_apply_trade_and_game_specific_absence():
    impact = client.get('/api/impact?alpha=1000&limit=500').json()['players']
    bos = [row for row in impact if row['team'] == 'BOS']
    den = [row for row in impact if row['team'] == 'DEN']

    scenario_body = {
        'as_of': '2026-01-15',
        'trials': 120,
        'seed': 91,
        'alpha': 1000,
        'trades': [{
            'player_a_id': bos[0]['player_id'],
            'player_b_id': den[0]['player_id'],
            'minutes_per_game': 34
        }],
        'absences': [{
            'player_id': bos[1]['player_id'],
            'games_missed': 20,
            'minutes_per_game': 30,
            'replacement_impact_per_100': 0
        }]
    }

    scenario = client.post('/api/scenario/player-absence', json=scenario_body)
    assert scenario.status_code == 200
    affected = next(
        row for row in scenario.json()['affected_games']
        if 'BOS' in {row['home_team'], row['away_team']}
    )

    request = {
        **scenario_body,
        'game_id': affected['game_id'],
        'prior_possessions': 300,
        'top_k': 3,
    }
    r = client.post('/api/scenario/game-lineups', json=request)
    assert r.status_code == 200
    data = r.json()

    bos_side = next(row for row in data['teams'] if row['team'] == 'BOS')
    roster_ids = {
        row['player_id']
        for row in bos_side['roster']['player_meta']
    }
    assert bos[0]['player_id'] not in roster_ids
    assert den[0]['player_id'] in roster_ids
    assert bos[1]['player_id'] not in roster_ids
    assert bos_side['lineups']
    assert len(bos_side['lineups'][0]['players']) == 5
