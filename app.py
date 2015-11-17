__author__ = 'jperelshteyn'

from flask import Flask, render_template, request, redirect, url_for, abort, session, jsonify
import process_headlines
import time
from pymongo import MongoClient
import twitter_manager
import headline_manager
import os


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
    option_list = headline_manager.get_headlines_for_ddl()
    return render_template('twitter_news.html', option_list=option_list)


@app.route('/_btnGetSargs_handler')
def btnGetSargs_handler():
    print 'here'
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
        hourly_sentiment, tweet_count = twitter_manager.get_hourly_sentiment(h_id)
        headline_score = headline_manager.get_s_score(headline)
        return jsonify(result=hourly_sentiment, tweet_count=tweet_count, headline_score=headline_score)


@app.context_processor
def override_url_for():
    return dict(url_for=dated_url_for)


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
