import requests
import re
import json
import trueskill
from datetime import datetime, timedelta
from app.player_mappings import player_name_mapping
from app.map_name_mapping import map_name_mapping
import time
from math import erf, sqrt
import matplotlib.pyplot as plt
from scipy.special import logit
import os


CACHE_FILE = "app/data/data_cache.json"
CACHE_DURATION = 900

player_games = {}



def cache_file_for_queue(queue):
    return f"app/data/data_cache_{queue}.json"


def save_to_cache(data, queue):
    with open(cache_file_for_queue(queue), 'w') as f:
        json.dump({
            'timestamp': time.time(),
            'data': data
        }, f)

def load_from_cache(queue):
    cache_file = cache_file_for_queue(queue)
    if os.path.exists(cache_file):
        with open(cache_file, 'r') as f:
            cached = json.load(f)
            if time.time() - cached['timestamp'] <= CACHE_DURATION:
                return cached['data']
    return None


def calculate_win_probability(rating1, rating2):
    delta_mu = rating1.mu - rating2.mu
    sum_sigma = rating1.sigma ** 2 + rating2.sigma ** 2
    x = delta_mu / sqrt(2 * (trueskill.BETA * trueskill.BETA) + sum_sigma)
    return 0.5 * (1 + erf(x / sqrt(2)))
    # return stats.norm.cdf(delta_mu / math.sqrt(2 * sum_sigma))

def calculate_win_probability_for_match(match, player_ratings):
    ts = trueskill.TrueSkill()
    # Calculate win probability of team
    team1_ratings = [player_ratings.get(player['user']['id'], ts.create_rating()) for player in match['players'] if player['team'] == 1]
    team2_ratings = [player_ratings.get(player['user']['id'], ts.create_rating()) for player in match['players'] if player['team'] == 2]


    # Calculate average rating using μ - 2σ
    team1_avg_rating = trueskill.Rating(
        mu=sum((rating.mu - 2*rating.sigma) for rating in team1_ratings),
        sigma=sum((rating.sigma**2) for rating in team1_ratings))
    team2_avg_rating = trueskill.Rating(
        mu=sum((rating.mu - 2*rating.sigma) for rating in team2_ratings),
        sigma=sum((rating.sigma**2) for rating in team2_ratings))

    win_prob_team1 = calculate_win_probability(team1_avg_rating, team2_avg_rating)
    return win_prob_team1

def apply_mappings(combined_data):
    mapping_applied_count = 0
    for match in combined_data:
        for player in match['players']:
            player_id = player['user']['id']
            if player_id in player_name_mapping:
                player['user']['name'] = player_name_mapping[player_id]
                mapping_applied_count += 1
    print(f"Applied mappings to {mapping_applied_count} players.")
    return combined_data

def fetch_data(start_date, end_date, queue):
    cached_data = load_from_cache(queue)
    if cached_data:
        return cached_data

    base_url = 'http://50.116.36.119/api/server/'
    
    # Define URL and JSON replace based on queue choice
    if queue == '2v2':
        urls = [base_url + '631438713183797258/games']
        json_replaces = ['datanaTA = ']
        queue_filters = ['2v2']
    elif queue == 'NA':
        urls = [base_url + '631438713183797258/games']
        json_replaces = ['datanaTA = ']
        queue_filters = ['PUGz']
    elif queue == 'EU':
        urls = [base_url + '539495516581658645/games']
        json_replaces = ['datata = ']
        queue_filters = ['PUG']
    elif queue == 'All':
        urls = [
            base_url + '631438713183797258/games', 
            base_url + '539495516581658645/games'
        ]
        json_replaces = ['datanaTA = ', 'datata = ']
        queue_filters = ['PUGz', 'PUG']
    else:
        raise ValueError(f"Invalid queue: {queue}")

    combined_data = []
    response_times = {}

    for url, json_replace, queue_filter in zip(urls, json_replaces, queue_filters):
        start_time = time.time()
        
        response = requests.get(url)
        
        end_time = time.time()
        response_time = end_time - start_time  # response time in seconds

        response_times[queue_filter] = response_time

        json_content = response.text.replace(json_replace, '')

        match = re.search(r'\[.*\]', json_content)
        if match:
            json_content = match.group(0)
            game_data = json.loads(json_content)
            
            # Filter for games
            filtered_data = [game for game in game_data
                             if game['queue']['name'] == queue_filter
                             and start_date <= datetime.fromtimestamp(game['timestamp'] / 1000) <= end_date]
            combined_data.extend(filtered_data)
        else:
            raise ValueError("No valid JSON data found in response.")
    
    print(f"Fetched {len(combined_data)} games for {queue} queue.")
    
    for q, r_time in response_times.items():
        print(f"Response time for {q} queue: {r_time:.4f} seconds.")

    mapped_data = apply_mappings(combined_data)
    save_to_cache(mapped_data, queue)    
    return mapped_data



def print_ratings(player_ratings, player_names):
    sorted_players = sorted(player_ratings.keys(), key=lambda x: (-player_ratings[x].mu, player_ratings[x].sigma))
    for player_id in sorted_players:
        rating = player_ratings[player_id]
        print(f"Player: {player_names[player_id]}, Mu: {rating.mu:.2f}, Sigma: {rating.sigma:.2f}")
def pick_order_sigma_adjustment(pick_order):

    # Define the range of sigma adjustments based on pick order
    sigma_min = 0.9  # 10% reduction for the best players
    sigma_max = 1.1  # 10% increase for the least picked players
    
    # Linear adjustment based on pick order; can be modified for a different curve
    return sigma_min + (sigma_max - sigma_min) * (pick_order - 1) / 11



def compute_logit_bonus(pick_order, total_picks=12, delta=0.015):
    """
    Computes the bonus to be added to mu based on the pick order using the logit function.
    """
    # Normalize the pick order so that 1 becomes almost 1 and 12 becomes almost 0, then raise it to a power for more aggressive decrease
    normalized_order = (total_picks - pick_order) / (total_picks -1)
    
    # Compute the logit value
    logit_value = logit(normalized_order * (1-(2*delta)) + delta)
    
    # Further adjust the scaling factor to make bonus even more aggressive
    bonus = 20 * logit_value / abs(logit(delta))
    
    return bonus


def calculate_ratings(game_data, queue='NA'):
    global player_names, player_picks 

    # Initialize TrueSkill
    ts = trueskill.TrueSkill()

    # Collect all player ids, their pick orders, and their wins
    all_player_ids = set(player['user']['id'] for match in game_data for player in match['players'])
    player_picks = {player_id: [] for player_id in all_player_ids}
    player_wins = {player_id: 0 for player_id in all_player_ids}
    player_names = {player['user']['id']: player['user']['name'] for match in game_data for player in match['players']}
    player_games = {player_id: 0 for player_id in all_player_ids}

    for match in game_data:
        for player in match['players']:
            player_games[player['user']['id']] += 1
            if player['pickOrder'] is not None and player['pickOrder'] > 0:  # Exclude captains and handle None
                player_picks[player['user']['id']].append(player['pickOrder'])
            if match['winningTeam'] == player['team']:
                player_wins[player['user']['id']] += 1

    # Compute average pick rates and win rates
    def recent_games_count(total_games):
        if total_games < 100:
            return total_games
        elif total_games < 150:
            return int(0.4 * total_games)
        else:
            return int(0.2 * total_games)

    player_avg_picks = {}
    player_win_rates = {}
    for player_id, picks in player_picks.items():
        recent_games = recent_games_count(len(picks))
        if recent_games == 0:
            player_avg_picks[player_id] = 0  # or any other value that makes sense in this context
        else:
            player_avg_picks[player_id] = sum(picks[-recent_games:]) / recent_games

    # Initialize the mu based on average pick and win rate
    def mu_bonus(pick_order):
        return compute_logit_bonus(pick_order)

    # Adjust the win rate for players with fewer games
    def adjusted_win_rate(win_rate, games_played):
        MIN_GAMES_FOR_FULL_IMPACT = 15
        if games_played < MIN_GAMES_FOR_FULL_IMPACT:
            adjusted_win_rate = win_rate * (games_played / MIN_GAMES_FOR_FULL_IMPACT) + 0.5 * (1 - games_played / MIN_GAMES_FOR_FULL_IMPACT)
            return adjusted_win_rate
        return win_rate

    # Adjust sigma for newer players and pick order
    def sigma_adjustment(games_played, pick_order):
        games_played_factor = 1.0
        if games_played < 10:
            games_played_factor = 1.5
        elif games_played < 30:
            games_played_factor = 1.25

        pick_order_factor = pick_order_sigma_adjustment(pick_order)  # Using the previously defined function
        return games_played_factor * pick_order_factor

    player_ratings = {}
    for player_id, avg_pick in player_avg_picks.items():
        # For players with less than 20 games
        if player_games[player_id] < 20:
            mu = 25
            sigma = 8.33333
        else:
            mu = ts.mu + mu_bonus(avg_pick)
            sigma = ts.sigma * sigma_adjustment(player_games[player_id], avg_pick)
        
        # Ensure mu ± 3*sigma lies within [0, 50]
        sigma = min(sigma, (50 - mu) / 3, mu / 3)
        
        player_ratings[player_id] = trueskill.Rating(mu=mu, sigma=sigma)

    # print("Initialized Ratings:")
    # print_ratings(player_ratings, player_names)
    # print("\n")

    # Process each match to adjust ratings
    for match in game_data:
        # Create a list of teams and corresponding player ID lists for the TrueSkill rate function
        teams = []
        team_player_ids = []
        for team_number in [1, 2]:
            team = [player_ratings[player['user']['id']] for player in match['players'] if player['team'] == team_number]
            player_ids = [player['user']['id'] for player in match['players'] if player['team'] == team_number]
            teams.append(team)
            team_player_ids.append(player_ids)

        # Adjust the team order if team 2 won the match
        if match['winningTeam'] == 2:
            teams.reverse()
            team_player_ids.reverse()

        # Update ratings based on match outcome
        new_ratings = ts.rate(teams)
        
        # Store the updated skill ratings
        for i, team in enumerate(teams):
            for j, player_rating in enumerate(team):
                player_ratings[team_player_ids[i][j]] = new_ratings[i][j]

    # print("Final Ratings after Match Processing:")
    # print_ratings(player_ratings, player_names)
    # print("\n")

    return player_ratings, player_names, player_games



def load_map_data(queue):
    filename = 'eu_maps_with_times.json' if queue == 'EU' else 'maps_with_times.json'
    with open(f'app/data/{filename}', 'r', encoding='utf-8') as f:
        return json.load(f)



def fetch_match_data(start_date, end_date, queue, player_ratings):
    
    game_data = fetch_data(start_date, end_date, queue)
    sorted_game_data = sorted(game_data, key=lambda game: game['timestamp'], reverse=True)

    map_data = load_map_data(queue)
    
    match_data = [
        {
            'match_id': i+1,
            'date': datetime.fromtimestamp(game['timestamp'] / 1000).strftime('%Y-%m-%d %H:%M'),
            'teams': [
                [player for player in game['players'] if player['team'] == team_number]
                for team_number in [1, 2]
            ],
            'winning_team': game['winningTeam'],
            'win_probability': calculate_win_probability_for_match(game, player_ratings),
            'maps': next((entry['maps'] for entry in map_data if game['timestamp'] <= entry['timestamp'] <= game['completionTimestamp']), None)
        }
        for i, game in enumerate(sorted_game_data)
    ]

    # Apply map name mapping
    for match in match_data:
        if match['maps']:
            match['maps'] = [map_name_mapping.get(map_name, map_name) for map_name in match['maps']]

    return match_data

def plot_player_quality_over_time_with_moving_avg(game_data, player_ratings, window_size=150):
    # Calculate average player quality for each match
    match_qualities = [
        sum([player_ratings[player['user']['id']].mu for player in game['players']]) / len(game['players'])
        for game in game_data
    ]
    
    # Calculate overall average player quality
    overall_avg_quality = sum(match_qualities) / len(match_qualities)
    
    # Calculate quality percentage for each match
    quality_percentages = [(match_quality / overall_avg_quality - 1) * 100 for match_quality in match_qualities]
    
    # Compute running average for the last `window_size` games
    moving_avg = []
    for i in range(len(quality_percentages)):
        if i < len(quality_percentages) - window_size + 1:
            avg = sum(quality_percentages[i:i+window_size]) / window_size
        else:
            avg = None
        moving_avg.append(avg)
    
    # Extract match dates for x-axis
    match_dates = [datetime.fromtimestamp(game['timestamp'] / 1000) for game in game_data]
    
    # Plot
    plt.figure(figsize=(12, 6))
    # plt.plot(match_dates, quality_percentages, label='Match Quality Percentage', color='blue', alpha=0.5)
    plt.plot(match_dates, moving_avg, label=f'Moving Average (Last {window_size} games)', color='green')
    plt.axhline(y=0, color='black', linestyle='--', label='Overall Average Quality')  # red line for average
    plt.xlabel('Date')
    plt.ylabel('Quality Percentage (%)')
    plt.title('Player Quality Over Time Compared to Overall Average')
    plt.legend()
    plt.grid(True, which='both', linestyle='--', linewidth=0.5)
    plt.tight_layout()
    plt.show()

# game_data = fetch_data(datetime(2018, 11, 1), datetime.now(), 'EU')
# player_ratings, _, _ = calculate_ratings(fetch_data(datetime(2018, 11, 1), datetime.now(), 'EU'), 'EU')
# plot_player_quality_over_time_with_moving_avg(game_data, player_ratings)

def calculate_win_rate_on_map_for_team(queue, map_name):
    # 1. Fetch match data for the specified queue
    player_ratings, _, _ = calculate_ratings(fetch_data(datetime(2018, 11, 1), datetime.now(), queue), queue)
    match_data = fetch_match_data(datetime(2018, 11, 1), datetime.now(), queue, player_ratings)

    # 2. Filter for matches on the specified map
    matches_on_map = [match for match in match_data if match['maps'] and map_name in match['maps']]

    # Count wins, ties, and losses for Team 1
    team1_wins = sum(1 for match in matches_on_map if match['winning_team'] == 1)
    ties = sum(1 for match in matches_on_map if match['winning_team'] == 0)
    team1_losses = sum(1 for match in matches_on_map if match['winning_team'] == 2)
    
    total_games_excluding_ties = team1_wins + team1_losses
    win_rate = team1_wins / total_games_excluding_ties * 100 if total_games_excluding_ties > 0 else 0

    return {
        'win_rate': win_rate,
        'wins': team1_wins,
        'ties': ties,
        'losses': team1_losses,
        'total_games': len(matches_on_map)
    }

# eu_stats = calculate_win_rate_on_map_for_team('EU', 'ss')
# na_stats = calculate_win_rate_on_map_for_team('NA', 'sunstar')

# print(f"Statistics for DS on Sunstar (EU):")
# print(f"Win rate: {eu_stats['win_rate']:.2f}%")
# print(f"Wins: {eu_stats['wins']}")
# print(f"Ties: {eu_stats['ties']}")
# print(f"Losses: {eu_stats['losses']}")
# print(f"Total games: {eu_stats['total_games']}")
# print("")

# print(f"Statistics for DS on Sunstar (NA):")
# print(f"Win rate: {na_stats['win_rate']:.2f}%")
# print(f"Wins: {na_stats['wins']}")
# print(f"Ties: {na_stats['ties']}")
# print(f"Losses: {na_stats['losses']}")
# print(f"Total games: {na_stats['total_games']}")


def compute_average_captain_time(queue):
    # Load game data and map data
    game_data = fetch_data(datetime(2018, 11, 1), datetime.now(), queue)
    map_data = load_map_data(queue)

    captain_times = {}  # Store the cumulative captain time for each player
    captain_counts = {}  # Store the number of times each player captained

    for game in game_data:
        # Check if the player was a captain and find the corresponding map timestamp
        for player in game['players']:
            if player['captain']:
                # Find the subsequent timestamp for the end of the match
                subsequent_timestamps = [entry['timestamp'] for entry in map_data if entry['timestamp'] > game['timestamp']]
                if subsequent_timestamps:
                    closest_subsequent_timestamp = min(subsequent_timestamps)
                    time_taken = (closest_subsequent_timestamp - game['timestamp']) / (60 * 1000)  # Convert to minutes
                    # Ensure the time taken is within a reasonable timeframe (e.g., 20 minutes)
                    if 0 <= time_taken <= 30:
                        player_name = player['user']['name']
                        captain_times[player_name] = captain_times.get(player_name, 0) + time_taken
                        captain_counts[player_name] = captain_counts.get(player_name, 0) + 1

    # Compute average captain time for each player
    average_captain_times = {player: total_time / captain_counts[player] for player, total_time in captain_times.items()}
    
    # Sort by average captain time, from longest to shortest
    sorted_times = sorted(average_captain_times.items(), key=lambda x: x[1], reverse=True)

    # Print the results
    for player, avg_time in sorted_times:
        print(f"{player}: {avg_time:.2f} minutes ({captain_counts[player]} times captained)")

# compute_average_captain_time('2v2')

def player_win_rate_on_maps(player_name, queue, team="0"):
    # 1. Fetch match data for the specified queue
    player_ratings, _, _ = calculate_ratings(fetch_data(datetime(2018, 11, 1), datetime.now(), queue), queue)
    match_data = fetch_match_data(datetime(2018, 11, 1), datetime.now(), queue, player_ratings)

    # 2. Filter for matches the player participated in based on the specified team
    if team == "0":
        player_matches = [match for match in match_data if any(player['user']['name'] == player_name for player in match['teams'][0] + match['teams'][1])]
    else:
        team_index = int(team) - 1
        player_matches = [match for match in match_data if any(player['user']['name'] == player_name for player in match['teams'][team_index])]

    # 3. Calculate win/loss/ties for each map
    map_winloss = {}
    for match in player_matches:
        if not match['maps']:
            continue

        for map_name in match['maps']:
            if map_name not in map_winloss:
                map_winloss[map_name] = {'wins': 0, 'losses': 0, 'ties': 0, 'total_games': 0}

            # Determine if the player was on the winning team, losing team or it was a tie
            if match['winning_team'] == 0:  # it's a tie
                map_winloss[map_name]['ties'] += 1
            elif any(player['user']['name'] == player_name for player in match['teams'][match['winning_team'] - 1]):
                map_winloss[map_name]['wins'] += 1
            else:
                map_winloss[map_name]['losses'] += 1

            map_winloss[map_name]['total_games'] += 1

    # 4. Calculate win rate for each map and sort by win rate
    map_winrates = {
        map_name: {
            'win_rate': (data['wins'] / (data['wins'] + data['losses'])) * 100 if (data['wins'] + data['losses']) > 0 else 0,
            'wins': data['wins'],
            'losses': data['losses'],
            'ties': data['ties'],
            'total_games': data['total_games']
        }
        for map_name, data in map_winloss.items()
    }
    sorted_winrates = sorted(map_winrates.items(), key=lambda item: (
        -1 if item[1]['total_games'] > 15 else item[1]['total_games'], 
        -item[1]['win_rate']
    ))

    return {
        map_name: {
            'win_rate': "{:.1f}".format(data['win_rate']),
            'wins': data['wins'],
            'losses': data['losses'],
            'ties': data['ties'],
            'total_games': data['total_games']
        }
        for map_name, data in sorted_winrates
    }



def augment_match_data_with_trueskill(match_data, player_ratings):
    for match in match_data:
        team1_ratings = [player_ratings[player['user']['id']] for player in match['teams'][0]]
        team2_ratings = [player_ratings[player['user']['id']] for player in match['teams'][1]]

        # Calculate average mu and sigma for each team
        match['team1_avg_mu'] = sum(rating.mu for rating in team1_ratings) / len(team1_ratings)
        match['team1_avg_sigma'] = sum(rating.sigma for rating in team1_ratings) / len(team1_ratings)
        match['team2_avg_mu'] = sum(rating.mu for rating in team2_ratings) / len(team2_ratings)
        match['team2_avg_sigma'] = sum(rating.sigma for rating in team2_ratings) / len(team2_ratings)

        # Calculate average TrueSkill (mu - 2*sigma) for each team
        match['team1_avg_trueskill'] = sum((rating.mu - 2*rating.sigma) for rating in team1_ratings) / len(team1_ratings)
        match['team2_avg_trueskill'] = sum((rating.mu - 2*rating.sigma) for rating in team2_ratings) / len(team2_ratings)
    
    return match_data

def calculate_accuracy(match_data):
    def accuracy_for_threshold(threshold, last_days=None, last_percent=None):
        if last_days:
            cutoff_date = datetime.now() - timedelta(days=last_days)
            recent_matches = [match for match in match_data if datetime.strptime(match['date'], '%Y-%m-%d %H:%M') > cutoff_date]
            
            # If there are fewer than 60 games in the last 90 days, consider the last 10% of games
            if len(recent_matches) < 60 and last_percent:
                number_to_consider = int(last_percent * len(match_data))
                recent_matches = match_data[:number_to_consider]
        else:
            recent_matches = match_data
        
        matches_above_threshold = [match for match in recent_matches if match['winning_team'] != 0 and (match['win_probability'] > threshold or match['win_probability'] < (1-threshold))]
        correct_predictions = [match for match in matches_above_threshold if 
                               (match['winning_team'] == 1 and match['win_probability'] > 0.5) or 
                               (match['winning_team'] == 2 and match['win_probability'] < 0.5)]
        
        accuracy = len(correct_predictions) / len(matches_above_threshold) if matches_above_threshold else 0
        return accuracy, len(correct_predictions), len(matches_above_threshold)

    accuracy_all, correct_all, total_all = accuracy_for_threshold(0.5)
    accuracy_55, correct_55, total_55 = accuracy_for_threshold(0.55)
    accuracy_60, correct_60, total_60 = accuracy_for_threshold(0.60)
    accuracy_65, correct_65, total_65 = accuracy_for_threshold(0.65)
    accuracy_all_90, correct_all_90, total_all_90 = accuracy_for_threshold(0.5, 90, 0.1)
    accuracy_55_90, correct_55_90, total_55_90 = accuracy_for_threshold(0.55, 90, 0.1)
    accuracy_60_90, correct_60_90, total_60_90 = accuracy_for_threshold(0.60, 90, 0.1)
    accuracy_65_90, correct_65_90, total_65_90 = accuracy_for_threshold(0.65, 90, 0.1)

    return {
        'all': (accuracy_all, correct_all, total_all),
        'above_55': (accuracy_55, correct_55, total_55),
        'above_60': (accuracy_60, correct_60, total_60),
        'above_65': (accuracy_65, correct_65, total_65),
        'all_90': (accuracy_all_90, correct_all_90, total_all_90),
        'above_55_90': (accuracy_55_90, correct_55_90, total_55_90),
        'above_60_90': (accuracy_60_90, correct_60_90, total_60_90),
        'above_65_90': (accuracy_65_90, correct_65_90, total_65_90)
    }

def simulate_mu_bonus_parameters(game_data, a_range, b_range, c_range):
    best_accuracy = 0
    best_params = None
    total_combinations = len(a_range) * len(b_range) * len(c_range)
    current_combination = 0
    start_time = time.time()
    print(f"Simulation Started")
    for a in a_range:
        for b in b_range:
            for c in c_range:
                # Update the mu_bonus function with the current values of a, b, c
                def mu_bonus(pick_order, win_rate):
                    bonus = a * pick_order**2 + b * pick_order + c
                    return bonus * win_rate

                # Use your rating calculation with the updated mu_bonus function
                player_ratings, _, _ = calculate_ratings(fetch_data(datetime(2018, 11, 1), datetime.now(), 'NA'), 'NA')

                # Fetch match data for accuracy calculation
                match_data = fetch_match_data(datetime(2018, 11, 1), datetime.now(), 'NA', player_ratings)
                accuracy_data = calculate_accuracy(match_data)
                
                # Check if this combination gives better accuracy than previously found
                if accuracy_data['all'][0] > best_accuracy:
                    best_accuracy = accuracy_data['all'][0]
                    best_params = (a, b, c)

                current_combination += 1
                if current_combination % (total_combinations // 20) == 0:  # 5% progress
                    elapsed_time = time.time() - start_time
                    print(f"{(current_combination / total_combinations) * 100:.2f}% done. Elapsed time: {elapsed_time:.2f}s")

    total_time = time.time() - start_time
    print(f"Simulation completed in {total_time:.2f}s")
    print(f"Best parameters found: a = {best_params[0]}, b = {best_params[1]}, c = {best_params[2]} with accuracy = {best_accuracy:.4f}")

# Define your search space for a, b, and c
a_range = [-0.7, -0.65, -0.6, -0.55, -0.5]
b_range = [0.3, 0.45, 0.6, 0.75, 0.9]
c_range = [-8.5, -8, -7.5, -7, -6.5]


game_data = fetch_data(datetime(2018, 11, 1), datetime.now(), 'NA')
# simulate_mu_bonus_parameters(game_data, a_range, b_range, c_range)
