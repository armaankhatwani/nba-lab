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
