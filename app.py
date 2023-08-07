from flask import Flask, render_template
import requests
import re
import json
import trueskill
from datetime import datetime
import math

app = Flask(__name__)

def fetch_data():
    # Fetch the data
    response = requests.get('https://sh4z.se/pugstats/naTA.json')

    # The content returned by the server is a string, so we need to parse it into a JSON object
    json_content = response.text.replace('datanaTA = ', '')

    match = re.search(r'\[.*\]', json_content)
    if match:
        json_content = match.group(0)
        game_data = json.loads(json_content) 
    else:
        raise ValueError("No valid JSON data found in response.")

    # Filter for games in the PUG queue and prepare match data
    game_data = [match for match in game_data if match['queue']['name'] == 'PUGz']

    return game_data

def decay_factor(timestamp, no_decay_period=90, half_life=365):
    # Current date
    current_date = datetime.now()

    # Game date
    game_date = datetime.fromtimestamp(timestamp / 1000)

    # Calculate the number of days since the game
    days_since_game = (current_date - game_date).days

    if days_since_game <= no_decay_period:
        # No decay within the no_decay_period
        decay = 1.0
    else:
        # Exponential decay with the given half-life
        decay = 0.8 ** ((days_since_game - no_decay_period) / half_life)

    return decay

def calculate_ratings(game_data):
    global player_names, player_picks  # Use the global variables

    # Initialize the TrueSkill environment
    ts = trueskill.TrueSkill()

    # Initialize the skill ratings for each player who was never a captain
    all_player_ids = set(player['user']['id'] for match in game_data for player in match['players'] if player['captain'] == 0)
    player_ratings = {player_id: ts.create_rating() for player_id in all_player_ids}
    player_names = {player['user']['id']: player['user']['name'] for match in game_data for player in match['players'] if player['captain'] == 0}

    # Initialize player pick orders for players who were never captains and when pickOrder is not None
    player_picks = {player_id: [] for player_id in all_player_ids}

    # Process each match
    for match in game_data:
        # Exclude the game if the player was a captain
        match_players = [player for player in match['players'] if player['captain'] == 0]

        # Record the pick order for each player who was not a captain and where pickOrder is not None
        for player in match_players:
            if player['pickOrder'] is not None:
                player_picks[player['user']['id']].append(player['pickOrder'])

        # Create a list of teams and corresponding player ID lists for the TrueSkill rate function
        teams = []
        team_player_ids = []
        for team_number in [1, 2]:
            team = [player_ratings[player['user']['id']] for player in match_players if player['team'] == team_number]
            player_ids = [player['user']['id'] for player in match_players if player['team'] == team_number]
            teams.append(team)
            team_player_ids.append(player_ids)

        # The teams should be ordered by rank (from best to worst), so we reverse the order if team 2 won
        if match['winningTeam'] == 2:
            teams.reverse()
            team_player_ids.reverse()

        # Update the skill ratings only for non-captain players
        new_ratings = ts.rate(teams, weights=[[decay_factor(match['timestamp'])] * len(team) for team in teams])

        # Store the updated skill ratings only for non-captain players
        for i, team in enumerate(teams):
            for j, player_rating in enumerate(team):
                decay = decay_factor(match['timestamp'])
                sigma_increase = 0.0 + 0.07 * (1 - decay)  # Increase sigma by 0% to 7% depending on decay
                player_ratings[team_player_ids[i][j]] = trueskill.Rating(mu=new_ratings[i][j].mu, sigma=new_ratings[i][j].sigma + sigma_increase)

    # Compute average pick rates
    player_pick_rates = {player_id: sum(picks) / len(picks) if picks else 0 for player_id, picks in player_picks.items()}

    # Modify the bonus function to accept pick order as a parameter
    def bonus(pick_order):
        # You can modify the coefficients a, b, and c to get the desired bonus values for each pick order
        a = 23
        b = 0.7
        c = 1
        return a * math.exp(-b * pick_order) - c * pick_order

    # Calculate and add the average bonus for each pick order
    for player_id, rating in player_ratings.items():
        pick_bonus = sum(bonus(pick) for pick in player_picks[player_id]) / len(player_picks[player_id]) if player_picks[player_id] else 0
        player_ratings[player_id] = trueskill.Rating(mu=rating.mu + pick_bonus, sigma=rating.sigma)

    return player_ratings, player_names

@app.route('/')
def home():
    game_data = fetch_data()
    player_ratings, player_names = calculate_ratings(game_data)

    # Sort players by trueskill rating
    sorted_player_ids = sorted(player_ratings, key=lambda x: player_ratings[x].mu - 3*player_ratings[x].sigma, reverse=True)

    # Format player names and ratings
    player_list = [
        f"{i+1}: {player_names[player_id]} trueskill {player_ratings[player_id].mu - 3*player_ratings[player_id].sigma:.2f} "
        f"(mu {player_ratings[player_id].mu:.1f}, sigma {player_ratings[player_id].sigma:.1f})"
        for i, player_id in enumerate(sorted_player_ids)
    ]

    return render_template('index.html', player_list=player_list)

if __name__ == "__main__":
    app.run(debug=True)
