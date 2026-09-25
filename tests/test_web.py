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
