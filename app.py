__author__ = 'jperelshteyn'

from flask import Flask, render_template, request, redirect, url_for, abort, session, jsonify
from pymongo import MongoClient
import os
from time import strftime, gmtime, time

from recipe_sorter import recipe_search
from twitter_monitor import twitter_manager, headline_manager
import pool


app = Flask(__name__)

@app.route('/')
def home():
    return render_template('projects.html')


@app.route('/about')
def about():
    return render_template('about.html')


@app.route('/projects')
def projects():
    return render_template('projects.html')


@app.route('/mta')
def mta():
    return render_template('mta.html')


@app.route('/movies')
def movies():
    return render_template('movies.html')


@app.route('/twitter_news')
def twitter_news():
    dates = get_dates_for_ddl()
    return render_template('twitter_news.html', dates=dates)


@app.route('/recipes')
def recipes():
    return render_template('recipes.html')


@app.route('/_btnGetSargs_handler')
def btnGetSargs_handler():
    h_id = request.args.get('id')
    h_text = request.args.get('text')
    if h_id and h_id != "0":
        # get sargs
        sargs = headline_manager.get_sargs_from_text(h_text)
        return jsonify(result=sargs)


@app.route('/_btnQuery_handler')
def btnQuery_handler():
    h_id = request.args.get('id')
    sargs = request.args.get('text')
    headline = request.args.get('headline')
    if sargs == 'testmode':
        h_id, sargs, headline = '56ae3df25fad558df56c18a4', 'mosquito weapon zika', 'New Weapon to Fight Zika: The Mosquito'
    if h_id:
        # query twitter
        twitter_manager.query(sargs, h_id)
        # process twitter results
        headline_score = headline_manager.get_s_score(headline)
        tweets = twitter_manager.read_db_tweets(h_id, sargs)
        g = twitter_manager.Graph(tweets, h_id)
        return jsonify(result=g.to_json(), 
                       tweet_count=g.tweet_count, 
                       headline_score=headline_score, 
                       scale=g.time_scale)

        # sentiment, tweet_count, scale = twitter_manager.get_sentiment_over_time(h_id, sargs)
        
        # return jsonify(result=sentiment, tweet_count=tweet_count, headline_score=headline_score, scale=scale)


@app.route('/_ddlDates_handler')
def ddlDates_handler():
    selected_date = request.args.get('date')
    headlines = headline_manager.get_headlines_for_ddl(selected_date)
    return jsonify(headlines=headlines)


def get_dates_for_ddl():
    dates = []
    current = gmtime()
    for days_back in range(0, 7):
        back_date = gmtime(time() - days_back * 86400)
        dates.append({'value': strftime("%m/%d/%y", back_date),
                      'text': strftime("%a, %b %d", back_date)})
    return dates


def dated_url_for(endpoint, **values):
    if endpoint == 'static':
        filename = values.get('filename', None)
        if filename:
            file_path = os.path.join(app.root_path,
                                     endpoint, filename)
            values['q'] = int(os.stat(file_path).st_mtime)
    return url_for(endpoint, **values)

## --------------------- Recipes ---------------------------------

@app.route('/_get_ingredients')
def get_ingredients():
    ingredients = recipe_search.get_ingredient_names()
    return jsonify(ingredients=ingredients)


@app.route('/_btnSearch_handler')
def btnSearch_handler():
    ingredients_csv = request.args.get('ingredients_csv')
    text_sarg = request.args.get('text_sarg')
    recipes = recipe_search.search(ingredients_csv, text_sarg, test=True)
    scored_recipes = recipe_search.sort_score_recipes(recipes)
    return jsonify(recipes=scored_recipes)


@app.context_processor
def override_url_for():
    return dict(url_for=dated_url_for)



## --------------------- Pool --------------------------------------------

@app.route('/pool')
def pool_app():
    return render_template('pool.html')

@app.route('/_get_players')
def get_players():
    players = pool.get_players()
    return jsonify(players=players)

@app.route('/_update_player')
def update_player():
    player = pool.Player()
    action = request.args.get('action')
    player_name = request.args.get('playerName')
    new_name = request.args.get('newName')
    success = False
    message = None
    if action == 'save':
        if player.is_duplicate(new_name):
            success = False
            message = 'name is already taken, please choose a different one'
        else:
            if player_name and new_name:
                player.update(player_name, new_name)
            else:
                player.save(new_name)
            success = True
    elif action == 'delete':
        success = player.delete(player_name)
    else:
        raise Exception('Unrecognized action: ' + action)
    return jsonify(success=success, message=message)

@app.route('/_record_game')
def record_game():
    winner = request.args.get('winner')
    loser = request.args.get('loser')
    success = pool.Game().save(winner, loser)
    return jsonify(success=success)

@app.route('/_get_top_players')
def get_top_players():
    return jsonify(topPlayers=pool.get_top_winners(5))





if __name__ == '__main__':
    #app.run(host='0.0.0.0', port=80)
    app.run(debug=True)
