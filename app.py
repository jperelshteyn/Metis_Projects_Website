__author__ = 'jperelshteyn'

from flask import Flask, render_template, request, redirect, url_for, abort, session, jsonify
from pymongo import MongoClient
from twitter_monitor import twitter_manager, headline_manager
import os
from time import strftime, gmtime, time
from recipe_sorter import recipe_search



app = Flask(__name__)

@app.route('/')
def home():
    return render_template('about.html')


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
    print h_id, sargs, headline
    if h_id:
        # query twitter
        twitter_manager.query(sargs, h_id)
        # process twitter results
        sentiment, tweet_count, scale = twitter_manager.get_sentiment_over_time(h_id, sargs)
        headline_score = headline_manager.get_s_score(headline)
        return jsonify(result=sentiment, tweet_count=tweet_count, headline_score=headline_score, scale=scale)


@app.route('/_ddlDates_handler')
def ddlDates_handler():
    selected_date = request.args.get('date')
    print selected_date
    headlines = headline_manager.get_headlines_for_ddl(selected_date)
    print headlines
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
    recipes = recipe_search.search(ingredients_csv, text_sarg, test=False)
    scored_recipes = recipe_search.sort_score_recipes(recipes)
    return jsonify(recipes=scored_recipes)


@app.context_processor
def override_url_for():
    return dict(url_for=dated_url_for)


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=80)
    #app.run(debug=True)
