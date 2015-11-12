__author__ = 'jperelshteyn'

from flask import Flask, render_template, request, redirect, url_for, abort, session, jsonify
import process_headlines
import time
from pymongo import MongoClient

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
    option_list = get_headlines()
    return render_template('twitter_news.html', option_list=option_list)


@app.route('/_ajax_handler')
def ajax_handler():
    s = request.args.get('selection')
    return jsonify(result=s)


def get_headlines():
	one_day_ago = time.time() - 8640
	one_week_ago = time.time() - 60480 
	client = MongoClient()
	db = client.twitter_news
	news_coll = db.news
	scores_coll = db.headline_scores
	cursor = news_coll.find({"time": {"$gt": one_day_ago}, "time": {"$lt": one_week_ago}})
	headlines = []
	for item in cursor:
	    h_id = item['_id']
	    h_text = item['headline']
	    scores = scores_coll.find_one({'headline_id': h_id})
	    if scores['s_score'] > 0 and len(scores['f_score']) > 1:
	        headlines.append({'text': h_text, 'id': h_id})
	return headlines


if __name__ == '__main__':
	app.run(debug=True)