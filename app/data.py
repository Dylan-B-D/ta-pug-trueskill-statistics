import requests
import re
import json
import trueskill
from datetime import datetime, timedelta
from app.player_mappings import player_name_mapping
from app.map_name_mapping import map_name_mapping
import time
from math import erf, sqrt
from scipy.special import logit
import os
import itertools
import math
from collections import defaultdict
import statistics


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


def win_probability(team1, team2):
    delta_mu = sum(r.mu for r in team1) - sum(r.mu for r in team2)
    sum_sigma = sum(r.sigma ** 2 for r in itertools.chain(team1, team2))
    size = len(team1) + len(team2)
    denom = math.sqrt(size * (trueskill.BETA * trueskill.BETA) + sum_sigma)
    ts = trueskill.global_env()
    return ts.cdf(delta_mu / denom)

def calculate_win_probability_for_match(match, player_ratings):
    ts = trueskill.TrueSkill()
    
    # Retrieve ratings for each player in the teams
    team1_ratings = [player_ratings.get(player['user']['id'], ts.create_rating()) for player in match['players'] if player['team'] == 1]
    team2_ratings = [player_ratings.get(player['user']['id'], ts.create_rating()) for player in match['players'] if player['team'] == 2]

    # Calculate win probability using the win_probability function
    win_prob_team1 = win_probability(team1_ratings, team2_ratings)
    
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
    try:
        cached_data = load_from_cache(queue)
        if cached_data:
            return cached_data
    except Exception as e:
        print(f"Error loading from cache: {e}")
        # We won't immediately refetch data here, but rather let it fall through 
        # to the fetching logic below. This way, if the cache fails, we just fetch 
        # fresh data as if the cache never existed.

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
        try:
            start_time = time.time()
            response = requests.get(url)
            end_time = time.time()
            
            if response.status_code != 200:
                raise ValueError(f"Unexpected status code {response.status_code} from {url}")

            response_time = end_time - start_time
            response_times[queue_filter] = response_time

            json_content = response.text.replace(json_replace, '')
            match = re.search(r'\[.*\]', json_content)
            
            if not match:
                raise ValueError("No valid JSON data found in response.")
            
            json_content = match.group(0)
            game_data = json.loads(json_content)

            # Filter for games
            filtered_data = [
                game for game in game_data
                if game['queue']['name'] == queue_filter
                and start_date <= datetime.fromtimestamp(game['timestamp'] / 1000) <= end_date
            ]
            
            combined_data.extend(filtered_data)
            
        except Exception as e:
            print(f"Error fetching or processing data from {url}: {e}")
            continue  # Skip to the next URL if there's an error with this one.

    print(f"Fetched {len(combined_data)} games for {queue} queue.")
    
    for q, r_time in response_times.items():
        print(f"Response time for {q} queue: {r_time:.4f} seconds.")

    try:
        mapped_data = apply_mappings(combined_data)
        save_to_cache(mapped_data, queue)
        return mapped_data
    except Exception as e:
        print(f"Error mapping or saving data: {e}")
        return None


def fetch_data_sh4z(start_date, end_date, queue):
    cached_data = load_from_cache(queue)
    if cached_data:
        return cached_data

    # Define URL, JSON replace, and queue filter based on queue choice
    if queue == '2v2':
        urls = ['https://sh4z.se/pugstats/naTA.json']
        json_replaces = ['datanaTA = ']
        queue_filters = ['2v2']
    elif queue == 'NA':
        urls = ['https://sh4z.se/pugstats/naTA.json']
        json_replaces = ['datanaTA = ']
        queue_filters = ['PUGz']
    elif queue == 'EU':
        urls = ['https://sh4z.se/pugstats/ta.json']
        json_replaces = ['datata = ']
        queue_filters = ['PUG']
    elif queue == 'All':
        urls = [
            'https://sh4z.se/pugstats/naTA.json',
            'https://sh4z.se/pugstats/ta.json'
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

# Ensure that you have the necessary functions like load_from_cache, apply_mappings, and save_to_cache defined elsewhere in your code.




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

def calculate_draw_rate(queue):
    game_data = fetch_data(datetime(2018, 11, 1), datetime.now(), queue)
    total_matches = len(game_data)
    draw_matches = sum(1 for game in game_data if game['winningTeam'] == 0)  # Assuming a winning team of 0 means a draw
    return draw_matches / total_matches if total_matches > 0 else 0


def calculate_ratings(game_data, queue='NA'):
    global player_names, player_picks 

    # Initialize TrueSkill
    draw_rate = calculate_draw_rate(queue)
    custom_tau = 0.1
    ts = trueskill.TrueSkill(draw_probability=draw_rate, tau=custom_tau) if queue != 'NA' else trueskill.TrueSkill(tau=custom_tau)


    # Initialize tracking variables
    all_player_ids = set(player['user']['id'] for match in game_data for player in match['players'])
    player_picks = {player_id: [] for player_id in all_player_ids}
    player_wins = {player_id: 0 for player_id in all_player_ids}
    player_names = {player['user']['id']: player['user']['name'] for match in game_data for player in match['players']}
    player_games = {player_id: 0 for player_id in all_player_ids}
    player_rating_history = {player_id: [] for player_id in all_player_ids}

    # Process each match
    for match in game_data:
        for player in match['players']:
            player_id = player['user']['id']
            player_games[player_id] += 1
            if player['pickOrder'] is not None and player['pickOrder'] > 0:
                player_picks[player_id].append(player['pickOrder'])
            if match['winningTeam'] == player['team']:
                player_wins[player_id] += 1

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

    # Initialize ratings
    player_ratings = {}
    for player_id, avg_pick in player_avg_picks.items():
        if queue != '2v2':
            mu = ts.mu + mu_bonus(avg_pick)
        else:
            mu = ts.mu
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
        try:
            # Update ratings based on match outcome
            new_ratings = ts.rate(teams)
        except FloatingPointError:
            # Handle numerical instability error
            continue
        
        # Store the updated skill ratings
        for i, team in enumerate(teams):
            for j, player_rating in enumerate(team):
                player_ratings[team_player_ids[i][j]] = new_ratings[i][j]

        for i, team in enumerate(teams):
            for j, player_rating in enumerate(team):
                player_id = team_player_ids[i][j]
                player_ratings[player_id] = new_ratings[i][j]
                
                # Convert Rating object to a dictionary
                rating_dict = {"mu": new_ratings[i][j].mu, "sigma": new_ratings[i][j].sigma}
                
                # Append the dictionary to player's rating history
                player_rating_history[player_id].append(rating_dict)

    # print("Final Ratings after Match Processing:")
    # print_ratings(player_ratings, player_names)
    # print("\n")

    return player_ratings, player_names, player_games, player_rating_history



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
    # plt.figure(figsize=(12, 6))
    # plt.plot(match_dates, quality_percentages, label='Match Quality Percentage', color='blue', alpha=0.5)
    # plt.plot(match_dates, moving_avg, label=f'Moving Average (Last {window_size} games)', color='green')
    # plt.axhline(y=0, color='black', linestyle='--', label='Overall Average Quality')  # red line for average
    # plt.xlabel('Date')
    # plt.ylabel('Quality Percentage (%)')
    # plt.title('Player Quality Over Time Compared to Overall Average')
    # plt.legend()
    # plt.grid(True, which='both', linestyle='--', linewidth=0.5)
    # plt.tight_layout()
    # plt.show()

# game_data = fetch_data(datetime(2018, 11, 1), datetime.now(), 'EU')
# player_ratings, _, _ = calculate_ratings(fetch_data(datetime(2018, 11, 1), datetime.now(), 'EU'), 'EU')
# plot_player_quality_over_time_with_moving_avg(game_data, player_ratings)

def calculate_win_rate_on_map_for_team(queue, map_name):
    # 1. Fetch match data for the specified queue
    player_ratings, _, _, _ = calculate_ratings(fetch_data(datetime(2018, 11, 1), datetime.now(), queue), queue)
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
    player_ratings, _, _, _ = calculate_ratings(fetch_data(datetime(2018, 11, 1), datetime.now(), queue), queue)
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

        # Calculate extended skill range for each team (min(mu - 2*sigma), max(mu + 2*sigma))
        match['team1_skill_range'] = (
            min(rating.mu - 2 * rating.sigma for rating in team1_ratings),
            max(rating.mu + 2 * rating.sigma for rating in team1_ratings),
        )
        match['team2_skill_range'] = (
            min(rating.mu - 2 * rating.sigma for rating in team2_ratings),
            max(rating.mu + 2 * rating.sigma for rating in team2_ratings),
        )
    
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

def compute_rgb(percentile):
    if percentile is None:
        return (255, 255, 255)  # default value or any other handling for None
    
    # Ensure percentile is a number
    try:
        percentile = float(percentile)
    except ValueError:
        # handle unexpected value, maybe log or raise a custom error
        raise ValueError(f"Unexpected value for percentile: {percentile}")

    percentile = max(0, min(100, percentile))

    if percentile > 50:
        # Lerp between yellow (255,255,0) and green (0,255,0)
        factor = (100 - percentile) / 50  # Adjust the factor to decrease red from 255 to 0
        red = int(255 * factor)
        green = 255
    else:
        # Lerp between yellow (255,255,0) and red (255,0,0)
        factor = percentile / 50
        red = 255
        green = int(255 * factor)
    return red, green, 0


epsilon = 1e-10

def calculate_percentile(value, dataset):
    dataset = [d for d in dataset if d is not None]  # Filter out None values

    if not dataset:  # Check if the dataset is empty after filtering
        return None

    if value == min(dataset):
        return epsilon
    elif value == max(dataset):
        return 100 - epsilon

    count = sum(1 for d in dataset if d < value)
    percentile = count / len(dataset) * 100
    return percentile

def calculate_percentile_inverse(value, dataset):
    dataset = [d for d in dataset if d is not None]  # Filter out None values

    if not dataset:  # Check if the dataset is empty after filtering
        return None

    if value == max(dataset):
        return epsilon
    elif value == min(dataset):
        return 100 - epsilon

    count = sum(1 for d in dataset if d > value)
    percentile = count / len(dataset) * 100
    return percentile


def ordinal(n):
    if 10 <= n % 100 <= 20:
        suffix = 'th'
    else:
        suffix = {1: 'st', 2: 'nd', 3: 'rd'}.get(n % 10, 'th')
    return f"{n}{suffix}"


def calculate_win_rate(player_name, game_data):
    total_games = 0
    wins = 0

    for game in game_data:
        if game['winningTeam'] == 0:
            continue

        for player in game['players']:
            if player['user']['name'] == player_name:
                total_games += 1
                if game['winningTeam'] == player['team']:
                    wins += 1

    if total_games == 0:
        return 0

    return wins / total_games * 100

def player_win_rate_percentile(player_name, game_data):
    all_players = set(player['user']['name'] for game in game_data for player in game['players'])
    all_players_win_rates = [calculate_win_rate(name, game_data) for name in all_players]
    player_win_rate = calculate_win_rate(player_name, game_data)
    
    return calculate_percentile(player_win_rate, all_players_win_rates)


def calculate_average_pick(player_name, game_data):
    total_pick_order = 0
    games = 0

    for game in game_data:
        for player in game['players']:
            pick_order = player.get('pickOrder')
            
            if player['user']['name'] == player_name and pick_order not in [None, 0]:
                total_pick_order += pick_order
                games += 1

    if games == 0:
        return 0

    return total_pick_order / games

def player_average_pick_percentile(player_name, game_data):
    all_players = set(player['user']['name'] for game in game_data for player in game['players'])
    all_players_avg_picks = [calculate_average_pick(name, game_data) for name in all_players]
    player_avg_pick = calculate_average_pick(player_name, game_data)
    
    return calculate_percentile_inverse(player_avg_pick, all_players_avg_picks)



def calculate_total_games(player_name, game_data):
    total_games = 0

    for game in game_data:
        for player in game['players']:
            if player['user']['name'] == player_name:
                total_games += 1
                break

    return total_games

def calculate_total_games(player_name, game_data):
    games = [1 for game in game_data for player in game['players'] if player['user']['name'] == player_name]
    return sum(games)

def player_total_games_percentile(player_name, game_data):
    all_players = set(player['user']['name'] for game in game_data for player in game['players'])
    all_players_total_games = [calculate_total_games(name, game_data) for name in all_players]
    player_total_games = calculate_total_games(player_name, game_data)
    
    return calculate_percentile(player_total_games, all_players_total_games)


def calculate_last_played(player_name, game_data):
    for game in reversed(game_data):
        for player in game['players']:
            if player['user']['name'] == player_name:
                last_played = datetime.fromtimestamp(game['timestamp'] / 1000)
                return time_ago(last_played)
    return None

def calculate_win_loss_tie(player_name, game_data):
    wins = 0
    losses = 0
    ties = 0

    for game in game_data:
        for player in game['players']:
            if player['user']['name'] == player_name:
                if game['winningTeam'] == 0:
                    ties += 1
                elif game['winningTeam'] == player['team']:
                    wins += 1
                else:
                    losses += 1
                break  # Break out of the inner loop once the player has been found in this game

    return wins, losses, ties

def calculate_peak_rating(player_id, player_rating_history):
    if player_id not in player_rating_history:
        return None

    if len(player_rating_history[player_id]) > 30:
        ratings = player_rating_history[player_id][30:]
    else:
        ratings = player_rating_history[player_id]
    
    peak = max(ratings, key=lambda x: x['mu'])
    return peak['mu']


def calculate_percentage_within_five_percent_of_peak(player_id, player_rating_history):
    if player_id not in player_rating_history:
        return "N/A"  

    peak = calculate_peak_rating(player_id, player_rating_history)
    
    if len(player_rating_history[player_id]) > 30:
        ratings = player_rating_history[player_id][30:]
    else:
        ratings = player_rating_history[player_id]
    
    within_range_count = sum(1 for rating in ratings if (0.95 * peak) <= rating['mu'] <= (1.05 * peak))
    
    percentage_within_range = (within_range_count / len(ratings)) * 100
    return f"{percentage_within_range:.2f}%"  # Returns the value as a formatted percentage string (e.g., "23.45%")


def calculate_rank_at_peak(player_id, player_rating_history):
    if player_id not in player_rating_history:
        return "N/A" 

    peak = calculate_peak_rating(player_id, player_rating_history)
    peak_index = next(i for i, rating in enumerate(player_rating_history[player_id]) if rating['mu'] == peak)
    
    all_ratings_at_peak = [player_ratings[peak_index]['mu'] for player_ratings in player_rating_history.values() if len(player_ratings) > peak_index]
    sorted_ratings = sorted(all_ratings_at_peak, reverse=True)
    rank = sorted_ratings.index(peak) + 1  # Add 1 because list indices start from 0
    return ordinal(rank)

def player_peak_rating_percentile(player_id, player_rating_history):

    # Get the peak rating for the specified player
    player_peak = calculate_peak_rating(player_id, player_rating_history)

    if player_peak is None:
        return None

    # Calculate the peak rating for each player and store in a list
    all_player_peaks = [calculate_peak_rating(pid, player_rating_history) for pid in player_rating_history.keys()]

    # Filter out any None values or the player's own peak for a fair comparison
    all_player_peaks = [peak for peak in all_player_peaks if peak is not None and peak != player_peak]

    # Calculate the percentile using the provided function
    percentile = calculate_percentile(player_peak, all_player_peaks)

    return percentile

def get_total_games_for_player(player_id, player_rating_history):
    return len(player_rating_history.get(player_id, []))


def player_percentage_within_five_percent_of_peak_percentile(player_id, player_rating_history):

    # Get the percentage for the specified player
    player_percentage = calculate_percentage_within_five_percent_of_peak(player_id, player_rating_history)

    # Convert it from string to float for calculations
    if player_percentage != "N/A":
        player_percentage = float(player_percentage.rstrip('%'))
    else:
        return None

    # Calculate the percentage for each player and store in a list
    all_player_percentages = []
    for pid in player_rating_history.keys():
        if get_total_games_for_player(pid, player_rating_history) > 30:
            percentage = calculate_percentage_within_five_percent_of_peak(pid, player_rating_history)
            if percentage != "N/A":
                all_player_percentages.append(float(percentage.rstrip('%')))

    # Calculate the percentile using the provided function
    percentile = calculate_percentile(player_percentage, all_player_percentages)

    return percentile

def ordinal_to_integer(ordinal_str):
    return int(''.join(filter(str.isdigit, ordinal_str)))

def player_rank_at_peak_percentile(player_id, players_rating_history):
    
    # Get the rank at peak for the specified player
    player_rank = calculate_rank_at_peak(player_id, players_rating_history)
    
    if player_rank == "N/A":
        return None
    
    # Convert the player's rank to an integer for calculations
    player_rank_int = ordinal_to_integer(player_rank)

    # Calculate the rank at peak for each player and store in a list
    all_player_ranks = [ordinal_to_integer(calculate_rank_at_peak(pid, players_rating_history)) for pid in players_rating_history if calculate_rank_at_peak(pid, players_rating_history) != "N/A"]
    
    # Calculate the percentile using the provided function
    percentile = calculate_percentile_inverse(player_rank_int, all_player_ranks)

    return percentile

def calculate_times_captained(player_name, game_data):
    captain_count = 0

    for game in game_data:
        for player in game['players']:
            if player['user']['name'] == player_name and player.get('pickOrder') == 0:
                captain_count += 1
                break  # Break out of the inner loop once the player has been found in this game

    return captain_count

def player_times_captained_percentile(player_name, game_data):
    # Get the times captained for the target player
    player_captained_count = calculate_times_captained(player_name, game_data)
    
    # Calculate the times captained for all players
    all_players = set(player['user']['name'] for game in game_data for player in game['players'])
    all_players_captained_counts = [calculate_times_captained(name, game_data) for name in all_players]
    
    # Calculate the percentile using the provided function
    percentile = calculate_percentile(player_captained_count, all_players_captained_counts)

    return percentile

def calculate_captain_winrate(player_name, game_data):
    captain_games = 0
    captain_wins = 0

    for game in game_data:
        if game['winningTeam'] == 0:  # Exclude ties
            continue

        for player in game['players']:
            if player['user']['name'] == player_name and player.get('pickOrder') == 0:
                captain_games += 1

                if game['winningTeam'] == player['team']:
                    captain_wins += 1

                break  # Break out of the inner loop once the player has been found in this game

    # Avoid division by zero if the player has never been a captain
    if captain_games == 0:
        return 0

    return (captain_wins / captain_games) * 100  # Return win rate as a percentage

def player_captain_winrate_percentile(player_name, game_data):
    all_players = set(player['user']['name'] for game in game_data for player in game['players'])

    # Get the captain winrates for all players who have captained at least once
    all_players_captain_winrates = [calculate_captain_winrate(name, game_data) for name in all_players if calculate_times_captained(name, game_data) > 0]

    # Calculate the captain winrate for the specified player
    player_captain_winrate = calculate_captain_winrate(player_name, game_data)

    # If the player hasn't captained, return None or an appropriate message
    if calculate_times_captained(player_name, game_data) == 0:
        return None  # Or return "The player hasn't captained."

    # Calculate the percentile using the provided function
    return calculate_percentile(player_captain_winrate, all_players_captain_winrates)

def calculate_captain_per_match_percentage(player_name, game_data):
    total_games_played = calculate_total_games(player_name, game_data)
    
    if total_games_played == 0:
        return 0  # To avoid division by zero. You can also return "N/A" or any other placeholder value.

    captain_count = calculate_times_captained(player_name, game_data)

    return (captain_count / total_games_played) * 100

def player_captain_per_match_percentile(player_name, game_data):
    player_percentage = calculate_captain_per_match_percentage(player_name, game_data)
    
    # Calculate "Captain per Match %" for all players
    all_players = set(player['user']['name'] for game in game_data for player in game['players'])
    all_players_percentages = [calculate_captain_per_match_percentage(name, game_data) for name in all_players]

    # Filter out players who have never been a captain for a fair comparison
    all_players_percentages = [percentage for percentage in all_players_percentages if percentage > 0]

    return calculate_percentile(player_percentage, all_players_percentages)

def calculate_average_captain_time(player_name, game_data, map_data):
    # Initialize the accumulative captain time and counts for the specific player
    captain_time = 0
    captain_count = 0

    for game in game_data:
        for player in game['players']:
            if player['captain'] and player['user']['name'] == player_name:
                # Find the subsequent timestamp for the end of the match
                subsequent_timestamps = [entry['timestamp'] for entry in map_data if entry['timestamp'] > game['timestamp']]
                if subsequent_timestamps:
                    closest_subsequent_timestamp = min(subsequent_timestamps)
                    time_taken = (closest_subsequent_timestamp - game['timestamp']) / (60 * 1000)  # Convert to minutes

                    # Ensure the time taken is within a reasonable timeframe (e.g., 20 minutes)
                    if 0 <= time_taken <= 30:
                        captain_time += time_taken
                        captain_count += 1

    if captain_count == 0:  # Avoid division by zero
        return 0
    
    avg_time_in_minutes = captain_time / captain_count
    return avg_time_in_minutes

def format_captain_time(avg_time_in_minutes):
    hours = int(avg_time_in_minutes // 60)
    minutes = int(avg_time_in_minutes % 60)
    seconds = int((avg_time_in_minutes * 60) % 60)  # Convert remaining minutes to seconds

    if hours > 0:
        return "{} hours {} mins {} sec".format(hours, minutes, seconds)
    else:
        return "{} mins {} sec".format(minutes, seconds)

def player_captain_time_percentile(player_name, game_data, map_data):
    player_time = calculate_average_captain_time(player_name, game_data, map_data)
    
    # Calculate average captain time for all players
    all_players = set(player['user']['name'] for game in game_data for player in game['players'])
    all_players_times = [calculate_average_captain_time(name, game_data, map_data) for name in all_players]

    # Filter out players who have never been a captain for a fair comparison
    all_players_times = [time for time in all_players_times if time > 0]

    return calculate_percentile_inverse(player_time, all_players_times)

def calculate_top_maps_picked_as_captain(player_name, game_data, map_data):
    # Map counter
    map_counts = {}

    for game in game_data:
        for player in game['players']:
            if player['captain'] and player['user']['name'] == player_name:
                match_timestamp = game['timestamp']

                # Find the closest timestamp in map_data that is not older than the match's timestamp
                subsequent_map_entries = [entry for entry in map_data if entry['timestamp'] >= match_timestamp]
                if subsequent_map_entries:
                    closest_map_entry = min(subsequent_map_entries, key=lambda x: x['timestamp'])
                    for map_name in closest_map_entry['maps']:
                        map_counts[map_name] = map_counts.get(map_name, 0) + 1

    # Sort maps by pick frequency and get the top
    sorted_maps = sorted(map_counts.items(), key=lambda x: x[1], reverse=True)
    top_maps = sorted_maps[:5]
    
    total_picks = sum(map_counts.values())
    
    # Format output using map_name_mapping and calculate the percentages
    output = []
    for map_name, count in top_maps:
        readable_name = map_name_mapping.get(map_name, map_name)  # Get readable name, default to map_name if not found in mapping
        percentage = (count / total_picks) * 100
        output.append(f"{readable_name} {percentage:.1f}%, ")
    
    return "\n".join(output)

def calculate_best_teammate(player_name, game_data):
    MIN_GAMES = 20
    NUM_TEAMMATES = 3
    games_played_with_teammate = defaultdict(int)
    teammate_winrates = defaultdict(int)
    
    for match in game_data:
        if match['winningTeam'] != 0:  # Skip ties
            for player in match['players']:
                if player['user']['name'] == player_name:
                    player_team = player['team']
                    teammates = [p for p in match['players'] if p['team'] == player_team and p['user']['name'] != player_name]
                    teammate_ids = [tm['user']['id'] for tm in teammates]
                    
                    for tm_id in teammate_ids:
                        games_played_with_teammate[tm_id] += 1
                        if match['winningTeam'] == player_team:
                            teammate_winrates[tm_id] += 1

    teammate_win_percentages = []
    for teammate_id, games_played in games_played_with_teammate.items():
        if games_played >= MIN_GAMES:  # Only consider teammates with whom the player has played at least 20 games
            win_percentage = (teammate_winrates[teammate_id] / games_played) * 100
            teammate_name = None
            for game in game_data:
                potential_name = next((p['user']['name'] for p in game['players'] if p['user']['id'] == teammate_id), None)
                if potential_name:
                    teammate_name = potential_name
                    break
            teammate_win_percentages.append((teammate_name, win_percentage))
    
    sorted_teammates = sorted(teammate_win_percentages, key=lambda x: x[1], reverse=True)

    top_teammates = [f"{name}: {percent:.2f}% win rate" for name, percent in sorted_teammates[:NUM_TEAMMATES]]

    return '\n'.join(top_teammates)

def calculate_longest_streaks(player_name, game_data):
    current_streak = 0
    streaks = []

    for game in game_data:
        player_team = None
        result = None  # Possible values: 'win', 'loss', or None
        player_participated = False

        # Check if the player participated in the game and which team they were on
        for player in game['players']:
            if player['user']['name'] == player_name:
                player_participated = True
                player_team = player['team']
                break

        # If the player didn't participate, skip this game
        if not player_participated:
            continue

        # If the player was in the game and their team won
        if player_team is not None and game['winningTeam'] == player_team:
            result = 'win'
        # If the player was in the game and their team lost
        elif player_team is not None and game['winningTeam'] != player_team and game['winningTeam'] != 0:
            result = 'loss'
        # If the game was a tie, continue to the next game
        elif game['winningTeam'] == 0:
            continue

        # If the current streak is in line with the game result, increment the streak
        if streaks and streaks[-1]['result'] == result:
            streaks[-1]['count'] += 1
        # If the current streak is different from the game result, start a new streak
        else:
            streaks.append({'result': result, 'count': 1})

    # Extract win and loss streaks separately
    win_streaks = sorted([s['count'] for s in streaks if s['result'] == 'win'], reverse=True)
    lose_streaks = sorted([s['count'] for s in streaks if s['result'] == 'loss'], reverse=True)

    def get_top_streaks(streak_list):
        from collections import Counter
        streak_counter = Counter(streak_list)
        sorted_streaks = sorted(streak_counter.items(), key=lambda x: x[0], reverse=True)
        top_streaks = []
        for streak, count in sorted_streaks:
            if count == 1:
                top_streaks.append(str(streak))
            else:
                top_streaks.append(f"{streak}x{count}")
            if len(top_streaks) == 3:  # Only take the top 3 streaks
                break
        return top_streaks

    # Calculate the top streaks for both win and lose
    top_win_streaks = get_top_streaks(win_streaks)
    top_lose_streaks = get_top_streaks(lose_streaks)

    return {
        "win_streaks": "\n".join(top_win_streaks),
        "lose_streaks": "\n".join(top_lose_streaks)
    }


def player_highest_streak(player_name, game_data, result_type="win"):
    """Calculate the highest win or loss streak for a player.
    
    Args:
        player_name (str): The name of the player.
        game_data (list): List of game data dictionaries.
        result_type (str): "win" to calculate win streak, "loss" to calculate loss streak.

    Returns:
        int: Highest streak count for the given result_type.
    """
    current_streak = 0
    highest_streak = 0

    for game in game_data:
        player_team = None
        player_result = None
        player_participated = False

        # Check if the player participated in the game and which team they were on
        for player in game['players']:
            if player['user']['name'] == player_name:
                player_participated = True
                player_team = player['team']
                break

        # If the player didn't participate, skip this game
        if not player_participated:
            continue

        if player_team is not None and game['winningTeam'] == player_team:
            player_result = 'win'
        elif player_team is not None and game['winningTeam'] != player_team and game['winningTeam'] != 0:
            player_result = 'loss'
        # If the game was a tie
        elif game['winningTeam'] == 0:
            continue

        # Update streaks based on win/loss
        if player_result == result_type:
            current_streak += 1
            highest_streak = max(highest_streak, current_streak)
        else:
            current_streak = 0  # Reset current streak

    return highest_streak

def player_win_streaks_percentile(player_name, game_data):
    player_streak = player_highest_streak(player_name, game_data, result_type="win")

    # Calculate highest win streak for all players
    all_players = set(player['user']['name'] for game in game_data for player in game['players'])
    all_players_streaks = [player_highest_streak(name, game_data, result_type="win") for name in all_players]

    return calculate_percentile(player_streak, all_players_streaks)

def player_loss_streaks_percentile(player_name, game_data):
    player_streak = player_highest_streak(player_name, game_data, result_type="loss")

    # Calculate highest loss streak for all players
    all_players = set(player['user']['name'] for game in game_data for player in game['players'])
    all_players_streaks = [player_highest_streak(name, game_data, result_type="loss") for name in all_players]

    return calculate_percentile_inverse(player_streak, all_players_streaks)


def calculate_longest_winrate_over_30_games(player_name, game_data):
    """Calculate the highest win rate over 30 consecutive games for a player.

    Args:
        player_name (str): The name of the player.
        game_data (list): List of game data dictionaries.

    Returns:
        float or str: Highest win rate over 30 games or "N/A" if less than 30 games played.
    """
    # Filter games where the player participated
    player_games = [game for game in game_data if any(player['user']['name'] == player_name for player in game['players'])]

    # If the player hasn't played at least 30 games, return "N/A"
    if len(player_games) < 30:
        return "N/A"

    max_winrate = 0

    # Loop through the player's games and calculate the win rate for every sequence of 30 games
    for i in range(len(player_games) - 29):
        games_slice = player_games[i:i+30]
        wins = sum(1 for game in games_slice if game['winningTeam'] == next(player['team'] for player in game['players'] if player['user']['name'] == player_name))
        winrate = wins / 30.0
        max_winrate = max(max_winrate, winrate)

    return max_winrate * 100  # Convert to percentage

def player_longest_winrate_over_30_games_percentile(player_name, game_data):

    player_winrate = calculate_longest_winrate_over_30_games(player_name, game_data)
    
    if player_winrate == "N/A":
        return "N/A"

    all_players = set(player['user']['name'] for game in game_data for player in game['players'])
    all_players_winrates = [calculate_longest_winrate_over_30_games(name, game_data) for name in all_players]

    all_players_winrates = [rate for rate in all_players_winrates if rate != "N/A"]

    return calculate_percentile(player_winrate, all_players_winrates)


def calculate_percentage_of_unexpected_outcomes(player_name, game_data, player_rating_history, expected_to_win):
    unexpected_outcomes = 0
    total_advantage_or_disadvantage_games = 0

    for idx, game in enumerate(game_data):
        player_team = None
        for player in game['players']:
            if player['user']['name'] == player_name:
                player_team = player['team']
                break

        if player_team is not None and game['winningTeam'] != 0:
            # Get ratings for this match from rating history
            current_ratings = {}
            for player in game['players']:
                player_id = player['user']['id']
                
                if player_id not in player_rating_history:
                    continue
                
                if idx < len(player_rating_history[player_id]):
                    current_ratings[player_id] = trueskill.Rating(mu=player_rating_history[player_id][idx]['mu'],
                                                                  sigma=player_rating_history[player_id][idx]['sigma'])
                else:
                    current_ratings[player_id] = trueskill.Rating(mu=player_rating_history[player_id][-1]['mu'],
                                                                  sigma=player_rating_history[player_id][-1]['sigma'])

            win_prob_team1 = calculate_win_probability_for_match(game, current_ratings)
            
            if expected_to_win:
                was_at_advantage = (player_team == 1 and win_prob_team1 >= 0.5) or (player_team == 2 and win_prob_team1 < 0.5)
                unexpected_outcome_condition = (player_team == 1 and game['winningTeam'] == 2) or (player_team == 2 and game['winningTeam'] == 1)
            else:
                was_at_advantage = (player_team == 1 and win_prob_team1 < 0.5) or (player_team == 2 and win_prob_team1 > 0.5)
                unexpected_outcome_condition = (player_team == 1 and game['winningTeam'] == 1) or (player_team == 2 and game['winningTeam'] == 2)
            
            if was_at_advantage:
                total_advantage_or_disadvantage_games += 1
                if unexpected_outcome_condition:
                    unexpected_outcomes += 1

    if total_advantage_or_disadvantage_games == 0:
        return 0

    return (unexpected_outcomes / total_advantage_or_disadvantage_games) * 100

def calculate_percentage_of_unexpected_wins(player_name, game_data, player_rating_history):
    return calculate_percentage_of_unexpected_outcomes(player_name, game_data, player_rating_history, expected_to_win=False)

def calculate_percentage_of_unexpected_losses(player_name, game_data, player_rating_history):
    return calculate_percentage_of_unexpected_outcomes(player_name, game_data, player_rating_history, expected_to_win=True)

def get_player_name_by_id(player_id, game_data):
    for game in game_data:
        for player in game['players']:
            if player['user']['id'] == player_id:
                return player['user']['name']
    return None

def player_percentage_of_unexpected_wins_percentile(player_name, game_data, player_rating_history):
    all_players_unexpected_wins = {}

    # Calculate unexpected wins for all players
    for player_id in player_rating_history.keys():
        player_name_from_id = get_player_name_by_id(player_id, game_data)
        if player_name_from_id:
            player_unexpected_wins = calculate_percentage_of_unexpected_wins(player_name_from_id, game_data, player_rating_history)
            all_players_unexpected_wins[player_name_from_id] = player_unexpected_wins

    # Calculate percentile for the specified player
    player_unexpected_wins = all_players_unexpected_wins.get(player_name)
    if player_unexpected_wins is None:
        return None

    return calculate_percentile(player_unexpected_wins, list(all_players_unexpected_wins.values()))

def player_percentage_of_unexpected_losses_percentile(player_name, game_data, player_rating_history):
    all_players_unexpected_losses = {}

    # Calculate unexpected losses for all players
    for player_id in player_rating_history.keys():
        player_name_from_id = get_player_name_by_id(player_id, game_data)
        if player_name_from_id:
            player_unexpected_losses = calculate_percentage_of_unexpected_losses(player_name_from_id, game_data, player_rating_history)
            all_players_unexpected_losses[player_name_from_id] = player_unexpected_losses


    # Calculate percentile for the specified player
    player_unexpected_losses = all_players_unexpected_losses.get(player_name)
    if player_unexpected_losses is None:
        return None

    return calculate_percentile_inverse(player_unexpected_losses, list(all_players_unexpected_losses.values()))



def calculate_consistency(player_name, game_data, player_rating_history):
    # Collect the performance metrics (e.g., player rating changes) over games
    player_ratings_changes = []
    win_loss_streaks = []
    current_streak = 0
    last_game_result = None

    for idx, game in enumerate(game_data):
        player_team = None
        for player in game['players']:
            if player['user']['name'] == player_name:
                player_team = player['team']
                if idx < len(player_rating_history[player['user']['id']]):
                    current_rating = player_rating_history[player['user']['id']][idx]['mu']
                    if idx > 0:
                        previous_rating = player_rating_history[player['user']['id']][idx-1]['mu']
                        player_ratings_changes.append(current_rating - previous_rating)
                break
        
        # Win/Loss streak calculation
        if player_team:
            game_result = 1 if game['winningTeam'] == player_team else 0
            if last_game_result is None:
                current_streak = 1
            elif last_game_result == game_result:
                current_streak += 1
            else:
                win_loss_streaks.append(current_streak)
                current_streak = 1
            last_game_result = game_result

    # End streak
    if current_streak != 0:
        win_loss_streaks.append(current_streak)

    if len(player_ratings_changes) < 2:
        print(f"Not enough rating changes for player {player_name} to calculate variance.")
        return None
    
    # Calculate variance of rating changes
    rating_variance = statistics.variance(player_ratings_changes)

    # Average streak
    avg_streak = sum(win_loss_streaks) / len(win_loss_streaks) if win_loss_streaks else 1

    # We'll invert the variance and normalize with the average streak to get consistency
    epsilon = 0.0001
    consistency = (1 / (rating_variance + epsilon)) * avg_streak


    print(f"For player {player_name}:")
    print(f"Win/Loss Streaks: {win_loss_streaks}")
    print(f"Rating Variance: {rating_variance}")
    print(f"Average Streak: {avg_streak}")
    print(f"Consistency: {consistency}")
    
    return consistency

def calculate_all_players_consistency(game_data, player_rating_history):
    all_players_consistency = {}
    for game in game_data:
        for player in game['players']:
            name = player['user']['name']
            if name not in all_players_consistency:
                all_players_consistency[name] = calculate_consistency(name, game_data, player_rating_history)
                
    sorted_players = sorted(all_players_consistency.items(), key=lambda x: (x[1] is None, x[1]), reverse=True)

    
    print("\nAll Players Sorted by Consistency (Highest to Lowest):")
    for player, cons_value in sorted_players:
        print(f"{player}: {cons_value}")

game_data = fetch_data(datetime(2018, 11, 1), datetime.now(), 'NA')
player_ratings, player_names, player_games, player_rating_history = calculate_ratings(game_data, 'NA')
calculate_all_players_consistency(game_data, player_rating_history)

def time_ago(past):
    now = datetime.now()

    # Time differences in different periods
    delta_seconds = (now - past).total_seconds()
    delta_minutes = delta_seconds / 60
    delta_hours = delta_minutes / 60
    delta_days = delta_hours / 24
    delta_weeks = delta_days / 7
    delta_months = delta_days / 30.44  # Average number of days in a month
    delta_years = delta_days / 365.25  # Average number of days in a year considering leap years

    # Determine which format to use based on the period
    if delta_seconds < 60:
        return "{} second(s) ago".format(int(delta_seconds))
    elif delta_minutes < 60:
        return "{} minute(s) ago".format(int(delta_minutes))
    elif delta_hours < 24:
        return "{} hour(s) ago".format(int(delta_hours))
    elif delta_days < 7:
        return "{} day(s) ago".format(int(delta_days))
    elif delta_weeks < 4.35:  # Approximately number of weeks in a month
        return "{} week(s) ago".format(int(delta_weeks))
    elif delta_months < 12:
        return "{} month(s) ago".format(int(delta_months))
    else:
        return "{} year(s) ago".format(int(delta_years))