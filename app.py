__author__ = 'jperelshteyn'

from flask import Flask, render_template, request, redirect, url_for, abort, session, jsonify
import process_headlines
from pymongo import MongoClient
import twitter_manager
import headline_manager
import os
from time import strftime, gmtime, time


app = Flask(__name__)

@app.route('/')
def home():
    return render_template('index.html')


@app.route('/mta')
def mta():
    return render_template('mta.html')


@app.route('/movies')
def movies():
    return render_template('movies.html')


@app.route('/twitter_news', methods=["GET", "POST"])
def twitter_news():
    dates = get_dates_for_ddl()
    #option_list = headline_manager.get_headlines_for_ddl('Sat, Nov 14')
    return render_template('twitter_news.html', dates=dates)


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
    if h_id:
    	print h_id
        # query twitter
        twitter_manager.query(sargs, h_id)
        # process twitter results
        sentiment, tweet_count, scale = twitter_manager.get_sentiment_over_time(h_id)
        print len(sentiment)
        headline_score = headline_manager.get_s_score(headline)
        return jsonify(result=sentiment, tweet_count=tweet_count, headline_score=headline_score, scale=scale)


@app.route('/_ddlDates_handler')
def ddlDates_handler():
    selected_date = request.args.get('date')
    headlines = headline_manager.get_headlines_for_ddl(selected_date)
    print headlines
    return jsonify(headlines=headlines)


@app.context_processor
def override_url_for():
    return dict(url_for=dated_url_for)


def get_dates_for_ddl():
    dates = []
    current = gmtime()
    for days_back in range(1, 8):
        back_date = time() - days_back * 86400 
        dates.append(strftime("%a, %b %d", gmtime(back_date)))
    return dates


def dated_url_for(endpoint, **values):
    if endpoint == 'static':
        filename = values.get('filename', None)
        if filename:
            file_path = os.path.join(app.root_path,
                                     endpoint, filename)
            values['q'] = int(os.stat(file_path).st_mtime)
    return url_for(endpoint, **values)


if __name__ == '__main__':
	app.run(debug=False)
