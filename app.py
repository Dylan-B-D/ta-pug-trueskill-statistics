from flask import Flask, render_template
from data import fetch_data, calculate_ratings
from flask import request
from datetime import datetime

app = Flask(__name__)

@app.route('/')
@app.route('/')
def home():
    return render_template('home.html')


@app.route('/rankings', methods=['GET', 'POST'])
def rankings():
    # Default date filters
    default_start_date = datetime(2021, 11, 1)
    default_end_date = datetime.now()

    # Get dates from form or default to current filter
    start_date_str = request.form.get('start_date', default=default_start_date.isoformat())
    end_date_str = request.form.get('end_date', default=default_end_date.isoformat())

    # Convert strings to datetime objects if they're not empty
    start_date = datetime.fromisoformat(start_date_str) if start_date_str else default_start_date
    end_date = datetime.fromisoformat(end_date_str) if end_date_str else default_end_date

    game_data = fetch_data(start_date, end_date)
    player_ratings, player_names = calculate_ratings(game_data)

    # Sort players by trueskill rating
    sorted_player_ids = sorted(player_ratings, key=lambda x: player_ratings[x].mu - 2*player_ratings[x].sigma, reverse=True)

    # Format player names and ratings
    player_list = [
        {
            "rank": i+1,
            "name": player_names[player_id],
            "trueskill": f"{player_ratings[player_id].mu - 2*player_ratings[player_id].sigma:.2f}",
            "mu": f"{player_ratings[player_id].mu:.1f}",
            "sigma": f"{player_ratings[player_id].sigma:.1f}",
        }
        for i, player_id in enumerate(sorted_player_ids)
    ]

    return render_template('rankings.html', player_list=player_list, start_date=start_date, end_date=end_date)

if __name__ == "__main__":
    app.run(debug=True)
