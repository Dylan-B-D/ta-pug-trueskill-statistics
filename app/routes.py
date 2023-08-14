from flask import render_template, request, jsonify
from app.data import fetch_data, calculate_ratings, fetch_match_data, augment_match_data_with_trueskill, calculate_win_probability_for_match, player_win_rate_on_maps
from datetime import datetime
from app import app
from app.player_mappings import player_name_mapping
from flask import redirect

@app.route('/')
def root():
    return redirect('/trueskill', code=302)

@app.route('/trueskill')
def home():
    return render_template('home.html')


@app.route('/rankings', methods=['GET', 'POST'])
def rankings():
    # Default date filters
    default_start_date = datetime(2018, 11, 1)
    default_end_date = datetime.now()

    # Get dates from form or default to current filter
    start_date_str = request.form.get('start_date', default=default_start_date.isoformat())
    end_date_str = request.form.get('end_date', default=default_end_date.isoformat())

    # Convert strings to datetime objects if they're not empty
    start_date = datetime.fromisoformat(start_date_str) if start_date_str else default_start_date
    end_date = datetime.fromisoformat(end_date_str) if end_date_str else default_end_date

    queue = request.form.get('queue', 'NA')
    game_data = fetch_data(start_date, end_date, queue)
    player_ratings, player_names, player_games = calculate_ratings(game_data, queue)

    min_games_str = request.form.get('min_games', '10')
    try:
        min_games = int(min_games_str)
    except ValueError:  # If the value cannot be converted to an integer
        min_games = 10  # Default to 10


    # Sort players by trueskill rating
    sorted_player_ids = sorted(player_ratings, key=lambda x: player_ratings[x].mu - 2*player_ratings[x].sigma, reverse=True)

    # Format player names, ratings, and games
    player_list = [
        {
            "id": player_id,
            "rank": i+1,
            "name": player_names[player_id],
            "trueskill": f"{player_ratings[player_id].mu - 2*player_ratings[player_id].sigma:.2f}",
            "mu": f"{player_ratings[player_id].mu:.1f}",
            "sigma": f"{player_ratings[player_id].sigma:.1f}",
            "games": player_games[player_id],
        }
        for i, player_id in enumerate(sorted_player_ids)
    ]

    # Filter player_list for players with a minimum number of games
    player_list = [player for player in player_list if player['games'] >= min_games]

    # Convert datetime objects back to strings
    start_date_str = start_date.strftime("%Y-%m-%d")
    end_date_str = end_date.strftime("%Y-%m-%d")

    return render_template('rankings.html', player_list=player_list, start_date=start_date_str, end_date=end_date_str, min_games=min_games, queue=queue)

@app.route('/match-history', methods=['GET', 'POST'])
def match_history():
    start_date = datetime(2018, 11, 1)
    end_date = datetime.now()
    
    if request.method == 'POST':
        queue = request.form.get('queue', 'NA')
    else:
        queue = request.args.get('queue', 'NA')
    
    # We get player ratings first since it's needed for both match_data and filtering
    game_data = fetch_data(start_date, end_date, queue)
    player_ratings, player_names, player_games = calculate_ratings(game_data, queue)
    
    # Fetch match data directly
    match_data = fetch_match_data(start_date, end_date, queue, player_ratings)
    
    player_name = request.args.get('player_search', None)
    print(f"Searching for player: {player_name}")
    if player_name:
        # Filter match_data instead of game_data
        match_data = [match for match in match_data if any(player['user']['name'] == player_name for team in match['teams'] for player in team)]

    match_data = augment_match_data_with_trueskill(match_data, player_ratings)

    # Set match index starting from the oldest
    for idx, match in enumerate(reversed(match_data), start=1):
        match['index'] = idx

    return render_template('match-history.html', match_data=match_data, queue=queue, player_name=player_name)

player_ratings_global = {}

@app.route('/team-calculator', methods=['GET', 'POST'])
def team_calculator():
    global player_ratings_global
    game_data = fetch_data(datetime(2018, 11, 1), datetime.now(), 'NA')
    player_ratings, player_names, _ = calculate_ratings(game_data, 'NA')
    sorted_player_ids = sorted(player_ratings, key=lambda x: player_ratings[x].mu - 2*player_ratings[x].sigma, reverse=True)
    player_ratings_global = player_ratings
    query = request.form.get('search_query', '').lower()
    player_list = [
        {
            "id": player_id,
            "rank": i+1,
            "name": player_names[player_id],
            "trueskill": f"{player_ratings[player_id].mu - 2*player_ratings[player_id].sigma:.2f}",
            "mu": f"{player_ratings[player_id].mu:.1f}",
            "sigma": f"{player_ratings[player_id].sigma:.1f}",
        }
        for i, player_id in enumerate(sorted_player_ids)
    ]
    player_list.sort(key=lambda x: float(x['trueskill']), reverse=True)
    
    match_data = fetch_match_data(datetime(2018, 11, 1), datetime.now(), 'NA', player_ratings)
    player_name = request.args.get('player_search', None)

    if player_name:
        match_data = [match for match in match_data if any(player['user']['name'] == player_name for team in match['teams'] for player in team)]

    match_data = augment_match_data_with_trueskill(match_data, player_ratings)
    last_match = match_data[0] if match_data else None

    return render_template('team-calculator.html', player_list=player_list, match_data=[last_match])

@app.route('/calculate_probability', methods=['POST'])
def calculate_probability():
    global player_ratings_global  
    
    team1_ids = request.form.getlist('team1[]')
    team2_ids = request.form.getlist('team2[]')

    pseudo_match = {
        'players': [
            {'user': {'id': int(player_id)}, 'team': 1} for player_id in team1_ids
        ] + [
            {'user': {'id': int(player_id)}, 'team': 2} for player_id in team2_ids
        ]
    }

    win_probability_team1 = calculate_win_probability_for_match(pseudo_match, player_ratings_global)
    return jsonify(win_probability=round(win_probability_team1 * 100, 2))


@app.route('/autocomplete_player')
def autocomplete_player():
    term = request.args.get('term', '')
    matching_players = [name for id, name in player_name_mapping.items() if term.lower() in name.lower()]
    return jsonify(matching_players)

@app.route('/player_stats', methods=['GET', 'POST'])
def player_stats():
    player_name = request.args.get('player_search') or request.form.get('player_search')
    
    if player_name:
        queue = request.args.get('queue', 'NA') or request.form.get('queue', 'NA')
        team = request.args.get('team', '0') or request.form.get('team', '0')
        player_data = player_win_rate_on_maps(player_name, queue, team)
    else:
        player_data = None
        player_name = None  # Make sure to set player_name to None if not present

    # Use the current filters when redirecting
    return render_template('player_stats.html', player_stats=player_data, player_name=player_name)
