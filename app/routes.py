from flask import render_template, request, jsonify
from app.data import fetch_data, calculate_ratings, fetch_match_data, augment_match_data_with_trueskill, calculate_win_probability_for_match, player_win_rate_on_maps, calculate_accuracy
from datetime import datetime
from app import app
from app.player_mappings import player_name_mapping
from app.map_url_mapping import map_url_mapping
from flask import redirect
from flask import send_from_directory
import os
from werkzeug.utils import secure_filename
from app.route_decoder import decode_route_file, mirror_route, reencrypt_route_file
from flask import flash
from werkzeug.utils import safe_join

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
    player_ratings, player_names, player_games = calculate_ratings(game_data, queue)

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
    player_ratings, player_names, player_games = calculate_ratings(game_data, queue)
    
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
    queue = request.args.get('queue', 'NA') or request.form.get('queue', 'NA')

    if player_name:
        team = request.args.get('team', '0') or request.form.get('team', '0')
        player_data = player_win_rate_on_maps(player_name, queue, team)
    else:
        player_data = None
        player_name = None  # Make sure to set player_name to None if not present

    # We get player ratings first since it's needed for both match_data and filtering
    game_data = fetch_data(datetime(2018, 11, 1), datetime.now(), queue)
    player_ratings, player_names, player_games = calculate_ratings(game_data, queue)
    
    # Fetch match data directly
    match_data = fetch_match_data(datetime(2018, 11, 1), datetime.now(), queue, player_ratings)
    
    if player_name:
        match_data_for_player = [match for match in match_data if any(player['user']['name'] == player_name for team in match['teams'] for player in team)]
        
        # Sort the matches by date, latest first (no need to reverse)
        sorted_match_data_for_player = sorted(match_data_for_player, key=lambda x: x['date'], reverse=True)
        
        # Augment sorted matches with TrueSkill and other metrics
        sorted_match_data_for_player = augment_match_data_with_trueskill(sorted_match_data_for_player, player_ratings)
        
        # Create lists of player names for each match
        for match in sorted_match_data_for_player:
            match['team1_names'] = [player['user']['name'] for player in match['teams'][0]]
            match['team2_names'] = [player['user']['name'] for player in match['teams'][1]]

        # Set match index starting from 1 for the oldest (so, reverse the sorted list for indexing)
        for idx, match in enumerate(sorted_match_data_for_player[::-1], start=1):
            match['index'] = idx

        all_matches_for_player = sorted_match_data_for_player  # All matches, not just the last 5

    else:
        all_matches_for_player = []

    match_class_color = {
        'win': '0, 128, 0',  # Green
        'loss': '255, 0, 0',  # Red
        'tie': '255, 255, 0'  # Yellow
    }
        
    return render_template('player_stats.html', match_class_color=match_class_color, all_matches_for_player=all_matches_for_player, player_stats=player_data, player_name=player_name, map_url_mapping=map_url_mapping)


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
