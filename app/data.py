import requests
import re
import json
import trueskill
from datetime import datetime
from app.player_mappings import player_name_mapping
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
    # Calculate win probability of team
    team1_ratings = [player_ratings[player['user']['id']] for player in match['players'] if player['team'] == 1]
    team2_ratings = [player_ratings[player['user']['id']] for player in match['players'] if player['team'] == 2]

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
    if queue == 'NA':
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

def calculate_ratings(game_data):
    global player_names, player_picks 

    # Initialize TrueSkill
    ts = trueskill.TrueSkill()

    # Initialize the skill ratings for each player who was never a captain
    all_player_ids = set(player['user']['id'] for match in game_data for player in match['players'] if player['captain'] == 0)
    player_ratings = {player_id: ts.create_rating() for player_id in all_player_ids}
    player_names = {player['user']['id']: player['user']['name'] for match in game_data for player in match['players'] if player['captain'] == 0}
    player_games = {player_id: 0 for player_id in all_player_ids}

    player_picks = {player_id: [] for player_id in all_player_ids}

    for match in game_data:
        # Exclude the game if the player was a captain
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

def fetch_match_data(start_date, end_date, queue, player_ratings):
    
    game_data = fetch_data(start_date, end_date, queue)
    sorted_game_data = sorted(game_data, key=lambda game: game['timestamp'], reverse=True)

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
        }
        for i, game in enumerate(sorted_game_data)
    ]

    return match_data

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

def get_player_game_count(player_name):
    # Get the player's ID from the name
    player_id = next((key for key, value in player_name_mapping.items() if value == player_name), None)
    
    # If the player ID is found in the player_games dictionary, return the game count. Otherwise, return 0.
    return player_games.get(player_id, 0)

