from __future__ import division
import sys
from math import log
from textblob import TextBlob as tb
from nltk.corpus import stopwords
from unicodedata import normalize
from nltk import stem
from nltk import wordnet
import numpy as np
from pymongo import MongoClient


lemma = wordnet.WordNetLemmatizer()

stop_words = set(stopwords.words('english'))
stop_chars = {',', '.', '?', '!', ';', ':', "'", '"'}
previous_headlines = None
blob_list = []


def main(arg):
    if arg:
        if arg[0] == '-score':
            score_and_save_headlines()
        if arg[0] == '-sarg':
            return best_sarg()


def tf(word, blob):
    return blob.words.count(word) / len(blob.words)


def n_containing(word, bloblist):
    return sum(1 for blob in bloblist if word in blob)


def idf(word, bloblist):
    return log(len(bloblist) / (1 + n_containing(word, bloblist)))


def tfidf(word, blob, bloblist):
    return tf(word, blob) * idf(word, bloblist)


def clean_word(word):
    clean_word = ''
    for c in u_to_a(word).lower():
        if c not in stop_chars:
            clean_word += c
    return clean_word
        

def clean_headline(headline):
    clean_headline = ''
    for w in headline.split():
        if w not in stop_words:
            w = clean_word(w)
            clean_headline += lemma.lemmatize(w.lower()) + ' '
    return clean_headline[:-1]


def split_headline(headline):
    return clean_headline(headline).split()


def blob_headline(headline):
    return tb(clean_headline(headline))


def get_previous_headlines(with_ids=False):
    client = MongoClient()
    db = client.twitter_news
    news_coll = db.news
    headlines = []
    for item in news_coll.find():
        if with_ids:
            headlines.append((item['_id'], clean_headline(item['headline'])))
        else:
            headlines.append(clean_headline(item['headline']))
    return headlines


def gen_previous_headline_words():
    client = MongoClient()
    db = client.twitter_news
    news_coll = db.news
    for item in news_coll.find():
         yield split_headline(headline)


def score_headline(headline_blob):
    global previous_headlines
    global blob_list
    if not previous_headlines:
        previous_headlines = get_previous_headlines()
    if not blob_list:
        for p_headline in previous_headlines:
            blob = tb(p_headline)
            blob_list.append(blob) 
    tfidf_scores = []
    for w in headline_blob.words:
        tfidf_scores.append((w, tfidf(w, headline_blob, blob_list)))
    tfidf_scores.sort(key=lambda tup: tup[1], reverse=True)
    return tfidf_scores


def u_to_a(u):
    '''Convert unicode to ASCII, if ASCII passed in than return it
    Args:
    u -- text to be converted 
    '''    
    if type(u) is unicode:
        return normalize('NFKD', u).encode('ascii','ignore')
    elif type(u) is str:
        return u


def score_and_save_headlines():
    processed_headline_ids = {}
    all_s_scores = []
    all_f_scores = []
    headline_scores = {}
    client = MongoClient()
    db = client.twitter_news
    score_coll = db.headline_scores
    previous_headlines = get_previous_headlines(True)
    # collect saved scores
    saved_scores = head_coll.find()
    if saved_scores.count() > 0:
        processed_headline_ids = {c[u'headline_id'] for c in saved_scores}
    for headline in previous_headlines:
        headline_id = headline[0]
        if headline_id not in processed_headline_ids:
            headline_blob = blob_headline(headline[1])
            s = headline_blob.sentiment
            s_score = abs(s.polarity * s.subjectivity)
            f_score = get_sargs(headline_blob)
            head_coll.insert({'headline_id': headline_id, 
                              'headline': headline[1], 
                              's_score': s_score, 
                              'f_score': f_score})


def best_sarg(count=5): 
    best = []
    headline_scores, all_s_scores, all_f_scores = read_headline_scores()
    all_f_scores = [s for s in all_f_scores if not np.isnan(s)]
    f_score_q90 = np.percentile(all_f_scores, 90)
    headline_scores_items = sorted(headline_scores.items(), key=lambda x: x[1][0], reverse=True)
    for headline, scores in headline_scores_items:
        if get_mean_f(scores[1]) > f_score_q90:
            best.append((headline, scores))
        if len(best) == int(count):    
            return best


def get_mean_f(f_scores):
    return np.mean([score for _, score in f_scores if not np.isnan(score)])
    
    
def get_sargs(headline_blob):
    sargs = []
    tfidf_scores = score_headline(headline_blob)
    word_tags = headline_blob.tags
    for word, score in tfidf_scores:
        if score > 0.5 and word in {word for word, tag in word_tags if tag in {u'NN', u'NNS'}}:
            sargs.append((word, score))
    return sargs  


def read_headline_scores():
    client = MongoClient()
    db = client.twitter_news
    head_coll = db.headline_scores
    all_s_scores = []
    all_f_scores = []
    headline_scores = {}
    for item in head_coll.find():
        headline_scores[item['headline']] = (item['s_score'], item['f_score'])
        all_s_scores.append(item['s_score'])
        all_f_scores.append(np.mean([score for _, score in item['f_score']]))
    return headline_scores, all_s_scores, all_f_scores


# if __name__ == '__main__':
#    main(sys.argv[1:])