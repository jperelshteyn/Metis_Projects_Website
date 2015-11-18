from __future__ import division
from dateutil.parser import parse
from tweepy import OAuthHandler
from tweepy import API
from tweepy import TweepError
import cnfg
from pymongo import MongoClient
import sys
from textblob import TextBlob as tb
from numpy import mean
from time import mktime
from math import floor
from bson.objectid import ObjectId
import pymongo
from dateutil.parser import parse
from time import mktime
import headline_manager


def initialize_api():
    config = cnfg.load(".twitter_config")
    auth = OAuthHandler(config["consumer_key"], config["consumer_secret"])
    auth.set_access_token(config["access_token"], config["access_token_secret"])
    api = API(auth, wait_on_rate_limit=True, wait_on_rate_limit_notify=True)
    return api

    
def query(sarg, headline_id, max_tweets=10000, tweets_per_qry=100, max_id=-1L, since_id=None):
    api = initialize_api()
    tweet_count = 0
    client = MongoClient()
    db = client.twitter_news
    tweet_coll = db.tweets
    saved_tweets = tweet_coll.find({'news_id': headline_id})
    saved_ids = {}
    if saved_tweets.count() > 0:
        saved_ids = {long(c[u'tweet_data'][u'id_str']) for c in saved_tweets}
        since_id = max(saved_ids)
    else:
        since_id = find_latest_tweet_id_before_headline(headline_id)
    while tweet_count < max_tweets:
        try:
            if (max_id <= 0):
                if (not since_id):
                    new_tweets = api.search(q=sarg, count=tweets_per_qry, lang='en')
                else:
                    new_tweets = api.search(q=sarg, count=tweets_per_qry, lang='en',
                                            since_id=since_id)
            else:
                if (not since_id):
                    new_tweets = api.search(q=sarg, count=tweets_per_qry, lang='en',
                                            max_id=str(max_id - 1))
                else:
                    new_tweets = api.search(q=sarg, count=tweets_per_qry, lang='en',
                                            max_id=str(max_id - 1),
                                            since_id=since_id)
            if not new_tweets:
                print("No more tweets found")
                break
            for tweet in new_tweets:
                if not long(tweet._json[u'id_str']) in saved_ids:
                    data = {}
                    data['news_id'] = headline_id
                    data['tweet_data'] = tweet._json
                    tweet_coll.insert(data)
            tweet_count += len(new_tweets)
            print("Downloaded {0} tweets".format(tweet_count))
            max_id = new_tweets[-1].id
        except TweepError as e:
            # Just exit if any error
            print("some error : " + str(e))
            break 


def get_sentiment_over_time(news_id):
    sentiment_by_time_list = []
    sentiment_by_time = {}
    client = MongoClient()
    db = client.twitter_news
    tweets = db.tweets.find({u'news_id': news_id})
    headline = db.news.find_one({u'_id': ObjectId(news_id)})
    publish_time = headline[u'time']
    headline_text = headline['headline']
    scale, denominator = get_time_scale(tweets)
    tweets = db.tweets.find({u'news_id': news_id})
    for tweet in tweets:
        tweet_time = get_tweet_time(tweet)
        tweet_text = tweet[u'tweet_data'][u'text']
        time_since = floor((tweet_time - publish_time) / denominator)
        if time_since > 0 and not is_retweet(tweet_text, headline_text):
            t_blob = tb(tweet_text)
            s = t_blob.sentiment
            s_score = abs(s.polarity)
            s_list = sentiment_by_time.get(time_since, [])
            s_list.append(s_score)
            sentiment_by_time[time_since] = s_list
    for time_period in sentiment_by_time:
        json_dict = {'time_period': time_period, 
                     'sentiment': mean(sentiment_by_time[time_period])}
        sentiment_by_time_list.append(json_dict)
    sentiment_by_time_list = sorted(sentiment_by_time_list, key=lambda x: x['time_period'])
    return sentiment_by_time_list, tweets.count(), scale


def get_time_scale(tweets):
    tweet_time = [get_tweet_time(t) for t in tweets]
    max_time = max(tweet_time)
    min_time = min([t for t in tweet_time if t >= 0])
    diff = max_time - min_time
    hour = 3600
    if diff > hour * 24 * 4:
        return 'days', hour * 24
    elif diff > hour * 4:
        return 'hours', hour
    else:
        return 'minutes', hour / 60


def get_tweet_time(tweet):
    dt = parse(tweet[u'tweet_data'][u'created_at'])
    return headline_manager.dt_to_epoch(dt.replace(tzinfo=None))


def find_latest_tweet_id_before_headline(headline_id):
    headline = headline_manager.get_headline_by_id(headline_id)
    h_time = headline['time']
    client = MongoClient()
    db = client.twitter_news
    db.tweets.ensure_index([("tweet_data.created_at", pymongo.DESCENDING)])
    cursor = db.tweets.find().sort([('tweet_data.created_at', pymongo.DESCENDING)])
    for tweet in cursor:
        dt = parse(tweet[u'tweet_data'][u'created_at'])
        tweet_time = mktime(dt.timetuple())
        if tweet_time < h_time:
            return tweet['tweet_data'][u'id']


def is_retweet(tweet, headline):
    if 'http' in tweet:
        tweet = tweet[:tweet.index('http')]
    return tweet.lower().strip() == headline.lower().strip()

