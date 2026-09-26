from fastapi.testclient import TestClient

from nba_lab.web import app

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


def test_scenario_api_can_return_rapm_sensitivity_ranges():
    r = client.post('/api/scenario/player-absence', json={
        'as_of': '2026-01-15',
        'trials': 120,
        'seed': 71,
        'alpha': 1000,
        'include_impact_sensitivity': True,
        'absences': [{
            'player_id': '1628369',
            'games_missed': 3,
            'minutes_per_game': 36,
            'replacement_impact_per_100': 0
        }]
    })
    assert r.status_code == 200
    data = r.json()
    assert data['impact_sensitivity']
    row = next(item for item in data['impact_sensitivity'] if item['team'] == 'BOS')
    altered = next(item for item in data['altered']['teams'] if item['team'] == 'BOS')
    assert row['expected_wins_min'] <= altered['expected_wins'] <= row['expected_wins_max']
    assert row['playoffs_probability_min'] <= altered['playoffs_probability'] <= row['playoffs_probability_max']
    assert row['championship_probability_min'] <= altered['championship_probability'] <= row['championship_probability_max']
