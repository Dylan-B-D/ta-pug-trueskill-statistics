from flask import render_template, request
from app.data import fetch_data, calculate_ratings, fetch_match_data, augment_match_data_with_trueskill
from datetime import datetime
from app import app


@app.route('/')
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
    player_ratings, player_names, player_games = calculate_ratings(game_data)

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

@app.route('/match_history', methods=['GET', 'POST'])
def match_history():
    start_date = datetime(2018, 11, 1)
    end_date = datetime.now()
    
    if request.method == 'POST':
        queue = request.form.get('queue', 'NA')
    else:
        queue = request.args.get('queue', 'NA')
    
    game_data = fetch_data(start_date, end_date, queue)
    player_ratings, player_names, player_games = calculate_ratings(game_data)
    match_data = fetch_match_data(start_date, end_date, queue, player_ratings)

    match_data = augment_match_data_with_trueskill(match_data, player_ratings)

    # Set match index starting from the oldest
    for idx, match in enumerate(reversed(match_data), start=1):
        match['index'] = idx

    return render_template('match_history.html', match_data=match_data, queue=queue)

