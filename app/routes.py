from flask import (render_template, request, jsonify, redirect, 
                   send_from_directory, flash)
from werkzeug.utils import secure_filename, safe_join
from app import app
from app.player_mappings import player_name_mapping
from app.map_url_mapping import map_url_mapping
from app.route_decoder import (decode_route_file, mirror_route, 
                               reencrypt_route_file)
from app.data import (
    fetch_data, 
    load_map_data,
    calculate_ratings, 
    fetch_match_data, 
    augment_match_data_with_trueskill, 
    calculate_win_probability_for_match, 
    player_win_rate_on_maps, 
    calculate_accuracy,
    calculate_win_rate,
    calculate_average_pick,
    calculate_total_games,
    calculate_last_played,
    player_average_pick_percentile,
    compute_rgb,
    player_win_rate_percentile,
    player_total_games_percentile,
    calculate_win_loss_tie,
    calculate_peak_rating,
    calculate_percentage_within_five_percent_of_peak,
    calculate_rank_at_peak,
    player_peak_rating_percentile,
    player_percentage_within_five_percent_of_peak_percentile,
    player_rank_at_peak_percentile,
    calculate_times_captained,
    player_times_captained_percentile,
    calculate_captain_winrate,
    player_captain_winrate_percentile,
    calculate_captain_per_match_percentage,
    player_captain_per_match_percentile,
    calculate_average_captain_time,
    player_captain_time_percentile,
    format_captain_time,
    calculate_top_maps_picked_as_captain,
    calculate_best_teammate,
)
import os
from datetime import datetime


files_to_delete_after_request = set()

UPLOAD_FOLDER = 'app/uploads'
ALLOWED_EXTENSIONS = {'route'}

app.config['UPLOAD_FOLDER'] = os.path.join(app.root_path, 'uploads')
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

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
    player_ratings, player_names, player_games, _ = calculate_ratings(game_data, queue)

    min_games_str = request.form.get('min_games', '30')
    try:
        min_games = int(min_games_str)
    except ValueError:  # If the value cannot be converted to an integer
        min_games = 30  # Default to 10


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
    player_ratings, player_names, player_games, _ = calculate_ratings(game_data, queue)
    
    # Fetch match data directly
    match_data = fetch_match_data(start_date, end_date, queue, player_ratings)
    
    player_name = request.args.get('player_search', None)
    print(f"Searching for player: {player_name}")
    if player_name:
        # Filter match_data instead of game_data
        match_data = [match for match in match_data if any(player['user']['name'] == player_name for team in match['teams'] for player in team)]

    match_data = augment_match_data_with_trueskill(match_data, player_ratings)
    
    accuracy_data = calculate_accuracy(match_data)
    # Set match index starting from the oldest
    for idx, match in enumerate(reversed(match_data), start=1):
        match['index'] = idx

    return render_template('match-history.html', match_data=match_data, queue=queue, player_name=player_name, accuracy_data=accuracy_data, map_url_mapping=map_url_mapping)



player_ratings_global = {}

@app.route('/team-calculator', methods=['GET', 'POST'])
def team_calculator():
    global player_ratings_global
    game_data = fetch_data(datetime(2018, 11, 1), datetime.now(), 'NA')
    player_ratings, player_names, _ , _= calculate_ratings(game_data, 'NA')
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
    queue = request.args.get('queue', 'NA') or request.form.get('queue', 'NA')
    map_data = load_map_data(queue)
    player_id = None  # Initialize player_id to None

    # Map player_name to player_id if possible
    if player_name:
        player_id = [k for k, v in player_name_mapping.items() if v == player_name]
        player_id = player_id[0] if player_id else None  # Take the first match if exists
    
    if player_name:
        team = request.args.get('team', '0') or request.form.get('team', '0')
        player_data = player_win_rate_on_maps(player_name, queue, team)
    else:
        player_data = None
        player_name = None

    game_data = fetch_data(datetime(2018, 11, 1), datetime.now(), queue)
    player_ratings, player_names, player_games, player_rating_history = calculate_ratings(game_data, queue)
    match_data = fetch_match_data(datetime(2018, 11, 1), datetime.now(), queue, player_ratings)
    
    if player_name:
        match_data_for_player = [match for match in match_data if any(player['user']['name'] == player_name for team in match['teams'] for player in team)]
        sorted_match_data_for_player = sorted(match_data_for_player, key=lambda x: x['date'], reverse=True)
        sorted_match_data_for_player = augment_match_data_with_trueskill(sorted_match_data_for_player, player_ratings)
        
        win_rate = calculate_win_rate(player_name, game_data)
        average_pick = calculate_average_pick(player_name, game_data)
        total_games = calculate_total_games(player_name, game_data)
        last_played = calculate_last_played(player_name, game_data)
        wins, losses, ties = calculate_win_loss_tie(player_name, game_data)
        avg_pick_percentile = player_average_pick_percentile(player_name, game_data)
        win_rate_percentile = player_win_rate_percentile(player_name, game_data)
        total_games_percentile = player_total_games_percentile(player_name, game_data)
        time_within_peak = calculate_percentage_within_five_percent_of_peak(player_id, player_rating_history)
        rank_at_peak = calculate_rank_at_peak(player_id, player_rating_history)
        max_rating_percentile = player_peak_rating_percentile(player_id, player_rating_history)
        five_from_peak_percentile = player_percentage_within_five_percent_of_peak_percentile(player_id, player_rating_history)
        rank_at_peak_percentile = player_rank_at_peak_percentile(player_id, player_rating_history)
        times_captained = calculate_times_captained(player_name, game_data)
        peak_rating = calculate_peak_rating(player_id, player_rating_history)
        times_captained_percentile = player_times_captained_percentile(player_name, game_data)
        captain_winrate = calculate_captain_winrate(player_name, game_data)
        captain_winrate_percentile = player_captain_winrate_percentile(player_name, game_data)
        captain_per_match_percentage = calculate_captain_per_match_percentage(player_name, game_data)
        captain_per_match_percentile = player_captain_per_match_percentile(player_name, game_data)
        avg_time = calculate_average_captain_time(player_name, game_data, map_data)
        average_captain_time = format_captain_time(avg_time)
        captain_time_percentile = player_captain_time_percentile(player_name, game_data, map_data)
        top_maps_picked_as_captain = calculate_top_maps_picked_as_captain(player_name, game_data, map_data)
        # best_teammate = calculate_best_teammate(player_name, game_data, player_ratings)

        if peak_rating is None:
            peak_rating = 'N/A'

        for match in sorted_match_data_for_player:
            match['team1_names'] = [player['user']['name'] for player in match['teams'][0]]
            match['team2_names'] = [player['user']['name'] for player in match['teams'][1]]

        for idx, match in enumerate(sorted_match_data_for_player[::-1], start=1):
            match['index'] = idx

        all_matches_for_player = sorted_match_data_for_player  # All matches, not just the last 5

    else:
        all_matches_for_player = []
        win_rate = None
        average_pick = None
        total_games = None
        last_played = None
        avg_pick_percentile = None
        win_rate_percentile = None
        total_games_percentile = None
        wins = None
        losses = None
        ties = None
        peak_rating = None
        time_within_peak = None
        rank_at_peak = None
        max_rating_percentile = None
        five_from_peak_percentile = None
        rank_at_peak_percentile = None
        times_captained = None
        times_captained_percentile = None
        captain_winrate = None
        captain_winrate_percentile = None
        captain_per_match_percentage = None
        captain_per_match_percentile = None
        average_captain_time = None
        captain_time_percentile = None
        top_maps_picked_as_captain = None
        # best_teammate = None
    

    return render_template(
        'player_stats.html', 
        player_rating_history=player_rating_history, 
        all_matches_for_player=all_matches_for_player, 
        player_stats=player_data, 
        player_name=player_name,
        player_id=player_id,
        win_rate=win_rate,
        average_pick=average_pick,
        avg_pick_percentile=avg_pick_percentile,
        win_rate_percentile=win_rate_percentile,
        total_games_percentile=total_games_percentile,
        total_games=total_games,
        last_played=last_played,
        wins=wins,
        losses=losses,
        ties=ties,
        peak=peak_rating,
        time_within_peak=time_within_peak,
        rank_peak=rank_at_peak,
        max_rating_percentile=max_rating_percentile,
        five_from_peak_percentile=five_from_peak_percentile,
        rank_at_peak_percentile=rank_at_peak_percentile,
        total_captained = times_captained,
        total_captained_percentile=times_captained_percentile,
        captain_winrate=captain_winrate,
        captain_winrate_percentile=captain_winrate_percentile,
        captain_per_match_percentage=captain_per_match_percentage,
        captain_per_match_percentile=captain_per_match_percentile,
        average_captain_time=average_captain_time,
        captain_time_percentile=captain_time_percentile,
        top_3_maps_picked_as_captain=top_maps_picked_as_captain,
        # best_teammate=best_teammate,
    )

@app.context_processor
def inject_compute_rgb():
    return dict(compute_rgb=compute_rgb)


@app.route('/route-decoder', methods=['GET', 'POST'])
def route_decoder():
    mirrored_file = None
    data = None  # This will hold the original data
    print(f"App root: {app.root_path}")

    if request.method == 'POST':
        if 'file' not in request.files:
            flash('No file part')
            return redirect(request.url)
        file = request.files['file']

        if file.filename == '':
            flash('No selected file')
            return redirect(request.url)
        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(filepath)

            # Decode to get the original data
            data, positions = decode_route_file(filepath)

            # Mirror the original data
            data_mirrored, positions_mirrored = mirror_route(data.copy(), positions.copy())  # Create a copy of the data and positions for mirroring

            # Modify the filename based on the mirrored team
            base_filename = filepath.rsplit('.', 1)[0]
            if "_DS_" in base_filename:
                base_filename = base_filename.replace("_DS_", "_BE_")
            else:
                base_filename = base_filename.replace("_BE_", "_DS_")
            mirrored_filepath = base_filename + ".route"

            output_file_reencrypted_mirrored = reencrypt_route_file(filepath, data_mirrored, positions_mirrored, mirrored_filepath)
            mirrored_file = os.path.basename(output_file_reencrypted_mirrored)
            os.remove(filepath)

    return render_template('route-decoder.html', mirrored_file=mirrored_file, data=data)  # Send the original data to the template



@app.route('/downloads/<filename>')
def download_file(filename):
    filepath = safe_join(app.config['UPLOAD_FOLDER'], filename)
    if not os.path.exists(filepath):
        return "File not found", 404
    files_to_delete_after_request.add(filepath)
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename, as_attachment=True)

@app.after_request
def cleanup_files_after_request(response):
    global files_to_delete_after_request
    for filepath in list(files_to_delete_after_request):  # Create a copy using list()
        try:
            os.remove(filepath)
            files_to_delete_after_request.remove(filepath)  # Remove from the original set
        except Exception as e:
            app.logger.error(f"Error deleting file {filepath}: {e}")
    return response
