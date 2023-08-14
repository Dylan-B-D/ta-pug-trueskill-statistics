import requests
import re
import json
import trueskill
from datetime import datetime
from app.player_mappings import player_name_mapping
from app.map_name_mapping import map_name_mapping
import math
from math import erf, sqrt

player_games = {}


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

def fetch_data(start_date, end_date, queue):
    if queue == '2v2':
        url = 'https://sh4z.se/pugstats/naTA.json'
        json_replace = 'datanaTA = '
        queue_filter = '2v2'
    elif queue == 'NA':
        url = 'https://sh4z.se/pugstats/naTA.json'
        json_replace = 'datanaTA = '
        queue_filter = 'PUGz'
    else:  # EU
        url = 'https://sh4z.se/pugstats/ta.json'
        json_replace = 'datata = '
        queue_filter = 'PUG'
        
    response = requests.get(url)

    # Parse conent into a JSON object
    json_content = response.text.replace(json_replace, '')

    match = re.search(r'\[.*\]', json_content)
    if match:
        json_content = match.group(0)
        game_data = json.loads(json_content) 
    else:
        raise ValueError("No valid JSON data found in response.")

    # Filter for games
    game_data = [game for game in game_data 
                 if game['queue']['name'] == queue_filter 
                 and start_date <= datetime.fromtimestamp(game['timestamp'] / 1000) <= end_date]
    

    for match in game_data:
        for player in match['players']:
            player_id = player['user']['id']
            if player_id in player_name_mapping:
                player['user']['name'] = player_name_mapping[player_id]

    return game_data

def decay_factor(timestamp, no_decay_period=90, half_life=365):
    
    current_date = datetime.now()
    game_date = datetime.fromtimestamp(timestamp / 1000)
    days_since_game = (current_date - game_date).days

    if days_since_game <= no_decay_period:
        # No decay
        decay = 1.0
    else:
        # Exponential decay with the given half-life
        decay = 0.8 ** ((days_since_game - no_decay_period) / half_life)

    return decay

def calculate_ratings(game_data, queue='NA'):
    global player_names, player_picks 

    # Initialize TrueSkill
    ts = trueskill.TrueSkill()

    # Initialize the skill ratings for each player who was never a captain
    all_player_ids = set(player['user']['id'] for match in game_data for player in match['players'])
    player_ratings = {player_id: ts.create_rating() for player_id in all_player_ids}
    player_names = {player['user']['id']: player['user']['name'] for match in game_data for player in match['players'] if player['captain'] == 0}
    player_games = {player_id: 0 for player_id in all_player_ids}

    player_picks = {player_id: [] for player_id in all_player_ids}

    for match in game_data:
        if queue == '2v2':
            # Include all players in 2v2
            match_players = match['players']
        else:
            # Exclude the game if the player was a captain for other queues
            match_players = [player for player in match['players'] if player['captain'] == 0]     

        # Record the pick order for each player who was not a captain and where pickOrder is not None
        for player in match_players:
            if player['pickOrder'] is not None:
                player_picks[player['user']['id']].append(player['pickOrder'])

            # Increment the game count for each player in the match
            player_games[player['user']['id']] += 1

        # Create a list of teams and corresponding player ID lists for the TrueSkill rate function
        teams = []
        team_player_ids = []
        for team_number in [1, 2]:
            team = [player_ratings[player['user']['id']] for player in match_players if player['team'] == team_number]
            player_ids = [player['user']['id'] for player in match_players if player['team'] == team_number]
            teams.append(team)
            team_player_ids.append(player_ids)

        if match['winningTeam'] == 2:
            teams.reverse()
            team_player_ids.reverse()

        new_ratings = ts.rate(teams, weights=[[decay_factor(match['timestamp'])] * len(team) for team in teams])

        # Store the updated skill ratings
        for i, team in enumerate(teams):
            for j, player_rating in enumerate(team):
                decay = decay_factor(match['timestamp'])
                sigma_increase = 0.0 + 0.07 * (1 - decay)  # Increase sigma by 0% to 7% depending on decay
                player_ratings[team_player_ids[i][j]] = trueskill.Rating(mu=new_ratings[i][j].mu, sigma=new_ratings[i][j].sigma + sigma_increase)

    # Compute average pick rates
    player_pick_rates = {player_id: sum(picks) / len(picks) if picks else 0 for player_id, picks in player_picks.items()}

    def bonus(pick_order):
        a = 23
        b = 0.7
        c = 1
        return a * math.exp(-b * pick_order) - c * pick_order

    # Calculate final rating
    for player_id, rating in player_ratings.items():
        pick_bonus = sum(bonus(pick) for pick in player_picks[player_id]) / len(player_picks[player_id]) if player_picks[player_id] else 0
        player_ratings[player_id] = trueskill.Rating(mu=rating.mu + pick_bonus, sigma=rating.sigma)
    

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

# compute_average_captain_time('EU')

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

