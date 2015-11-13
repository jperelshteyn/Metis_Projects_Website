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


def initialize_api():
    config = cnfg.load(".twitter_config")
    auth = OAuthHandler(config["consumer_key"], config["consumer_secret"])
    auth.set_access_token(config["access_token"], config["access_token_secret"])
    api = API(auth, wait_on_rate_limit=True, wait_on_rate_limit_notify=True)
    return api

    
def query(sarg, news_id, max_tweets=10000, tweets_per_qry=100, max_id=-1L, since_id=None):
    api = initialize_api()
    tweet_count = 0
    client = MongoClient()
    db = client.twitter_news
    tweet_coll = db.tweets
    saved_tweets = tweet_coll.find({'news_id': news_id})
    saved_ids = {}
    if saved_tweets.count() > 0:
        saved_ids = {long(c[u'tweet_data'][u'id_str']) for c in saved_tweets}
        since_id = max(saved_ids)
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
                    data['news_id'] = news_id
                    data['tweet_data'] = tweet._json
                    tweet_coll.insert(data)
            tweet_count += len(new_tweets)
            print("Downloaded {0} tweets".format(tweet_count))
            max_id = new_tweets[-1].id
        except TweepError as e:
            # Just exit if any error
            print("some error : " + str(e))
            break 


def get_hourly_sentiment(news_id):
    hourly_sentiment_list = []
    hourly_sentiment = {}
    client = MongoClient()
    db = client.twitter_news
    tweets = db.tweets.find({u'news_id': news_id})
    print 'tweet count', tweets.count()
    headline = db.news.find_one({u'_id': ObjectId(news_id)})
    publish_time = headline[u'time']
    for tweet in tweets:
        dt = parse(tweet[u'tweet_data'][u'created_at'])
        tweet_time = mktime(dt.timetuple())
        text = tweet[u'tweet_data'][u'text']
        t_blob = tb(text)
        s = t_blob.sentiment
        s_score = abs(s.polarity * s.subjectivity)
        hours_since = int(floor((tweet_time - publish_time) / 3600))
        if hours_since > 0:
            s_list = hourly_sentiment.get(hours_since, [])
            s_list.append(s_score)
            hourly_sentiment[hours_since] = s_list
    for hour in hourly_sentiment:
        json_dict = {'hour': hour, 'sentiment': mean(hourly_sentiment[hour])}
        hourly_sentiment_list.append(json_dict)
    return sorted(hourly_sentiment_list, key=lambda x: x['hour']), tweets.count()


def is_retweet(tweet, headline):
    if 'http' in tweet:
        tweet = tweet[:tweet.index('http')]
    return tweet.lower().strip() == headline.lower().strip()

