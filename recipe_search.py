from __future__ import division
import requests
import cnfg
import json
from pymongo import MongoClient
import traceback


client = MongoClient()
db = client.recipes
config = cnfg.load(".recipe_config")
stop_chars = {',', '.', '?', '!', ';', ':', "'", '"', ')', '('}
db_ingredients = []



class Genre:

    def __init__(self, name=None, adjective_ids=[], scraped_adjectives=None, _id=None):
        self.name = name
        self.scraped_adjectives = scraped_adjectives
        self.adjective_ids = adjective_ids
        self._id = _id
    
    def to_json(self):
        return {'_id': self._id,
                'name': self.name,
                'adjective_ids': self.adjective_ids,
                'scraped_adjectives': self.scraped_adjectives}
    
    def for_web(self):
        json = self.to_json
        del json['adjective_ids']
        del json['scraped_adjectives']
        return json
    
    def get(self):
        assert db.name == 'recipes'
        sarg = {'_id': self._id} if self._id else {'name': self.name}
        data = db.genres.find_one(sarg)
        if data:
            self._id = data['_id']
            self.name = data['name']
            self.adjective_ids = data['adjective_ids']
            self.scraped_adjectives = data['scraped_adjectives']
            
    def save(self):
        assert db.name == 'recipes'
        data = self.to_json()
        if self._id:
            db.genres.update({'_id': self._id}, data)
        else:
            self._id = db.genres.insert(data)
        return self._id
    
    def associate_adjective(self, adjective_id):
        assert type(adjective_id) is ObjectId
        self.adjective_ids = list(set(self.adjective_ids + [adjective_id]))
        self.save()
        
    def get_adjectives(self):
        adjectives = set(self.scraped_adjectives)
        for adj_id in self.adjective_ids:
            adj = Adjective(_id = adj_id)
            adj.get()
            adjectives.update(set(adj.synonyms))
        return adjectives


class Ingredient:

    def __init__(self, name=None, _id=None):
        assert db.name == 'recipes'
        assert name or _id
        data = None
        if _id:
            if type(_id) is str:
                data = db.ingredients.find_one({'_id': ObjectId(_id)})
            elif type(_id) is ObjectId:
                data = db.ingredients.find_one({'_id': _id})
        elif name:
            name = name.lower()
            data = db.ingredients.find_one({'name': name}) or \
                   db.ingredients.find_one({'name': {'$regex': '.*'+name+'.*'}})
            if not data and len(name.split()) > 1:
                for word in name.split():
                    data = db.ingredients.find_one({'name': name}) or \
                           db.ingredients.find_one({'name': {'$regex': '.*'+name+'.*'}})
                    if data:
                        break
        if data: 
            self.name = data['name']
            self._id = data['_id']
            self.description = data['description']
            self.adjective_ids = data['adjective_ids']
            self.poem_ids = data['poem_ids']
            self.valid = data['valid']
            self.source = data['source']
            self.genre_scores = data['genre_scores']
        else:
            self = None

    def associate_poem(self, poem_id):
        assert type(poem_id) is str or type(poem_id) is ObjectId
        assert db.name == 'recipes'
        data = db.ingredients.find_one({'_id': self._id})
        poem_id = poem_id if type(poem_id) is ObjectId else ObjectId(poem_id)        
        data['poem_ids'] = list(set(data['poem_ids'] + [poem_id]))
        db.ingredients.update({'_id': self._id}, data)
        
    def associate_adjective(self, adjective_id):
        assert type(adjective_id) is str or type(adjective_id) is ObjectId
        assert db.name == 'recipes'
        data = db.ingredients.find_one({'_id': self._id})
        data['adjective_ids'] = list(set(data['adjective_ids'] + [adjective_id]))
        db.ingredients.update({'_id': self._id}, data)

    def get_poem_texts(self):
        assert db.name == 'recipes'
        return [p['text'] for p in db.poems.find({'_id':{'$in': self.poem_ids}})]
    
    def get_adjectives(self):
        adjectives = []
        for adj_id in self.adjective_ids:
            adj = Adjective(_id = adj_id)
            adj.get()
            adjectives.append(adj.word)
            adjectives += adj.synonyms
        return adjectives
    
    def update_genre_scores(self, genre_id):
        adjective_scores = {}
        genre = Genre(_id=genre_id)
        genre.get()
        genre_adjectives = set(genre.adjectives)
        ingredient_adjectives = self.get_adjectives()
        word_freq = 1/len(ingredient_adjectives)
        for ingr_adj in ingredient_adjectives:
            if ingr_adj in genre_adjectives:
                adjective_scores[ingr_adj] = \
                    adjective_scores.get(ingr_adj, 0) + word_freq
        self.genre_scores[genre_id] = adjective_scores
        self.save()
    
    def save(self):
        data = {'name': self.name,
                '_id': self._id,
                'description': self.description,
                'adjective_ids': self.adjective_ids,
                'poem_ids': self.poem_ids,
                'valid': self.valid,
                'source': self.source,
                'genre_scores': self.genre_scores}
        db.ingredients.update({'_id': self._id}, data)

        
class Recipe:
    
    def __init__(self, name='', 
                 raw_ingredients=[], 
                 ingredients=[], 
                 url='', 
                 source='', 
                 json={}):
        assert type(ingredients) is list
        if json:
            self.name = json['name']
            self.raw_ingredients = json['raw_ingredients']
            self.ingredients = json['ingredients']
            self.url = json['url']
            self.source = json['source']
            self.adjectives = None
        else:
            self.name = name
            self.raw_ingredients = raw_ingredients
            self.ingredients = ingredients
            self.url = url
            self.source = source
            self.adjectives = None
    
    def to_json(self):
        return {'name': self.name,
                'raw_ingredients': self.raw_ingredients,
                'ingredients': self.ingredients, 
                'url': self.url, 
                'source': self.source,
                'adjectives': self.adjectives}

    def extract_ingredients(self):
        global real_ingredients
        self.ingredients = []
        for line in self.raw_ingredients:
            words = [clean_word(w) for w in line.split()]
            two_words = set(words[ind-1] +' '+ word for ind, word in enumerate(words) if ind > 0)
            pure = real_ingredients & two_words
            if not pure:
                pure = real_ingredients & set(words)
            if pure:
                self.ingredients.append(pure.pop())

    def for_web(self):
        json = self.to_json()
        del json['adjectives']
        return json

    def save(self):
        assert db.name == 'recipes'
        data = self.to_json()
        return db.recipes.insert(data)        

    def get_adjectives(self):
        adjectives = []
        for ingr_name in self.ingredients:
            ingr = Ingredient(ingr_name)
            if hasattr(ingr, '_id'):
                adjectives += ingr.get_adjectives()
        self.adjectives = adjectives
    
    def get_genre_scores(self, genres):
        genre_scores = {g: {} for g in genres}
        for ingr_name in self.ingredients:
            ingr = Ingredient(ingr_name)
            if hasattr(ingr, '_id'):
                for genre in ingr.genre_scores:
                    for adj in ingr.genre_scores[genre]:
                        genre_scores[genre][adj] = genre_scores[genre].get(adj, 0) \
                                                    + ingr.genre_scores[genre][adj]
        return genre_scores
                    


class Poem:

    def __init__(self, title='', author='', text='', is_professional=True, _id=None):
        self.title = title.lower()
        self.author = author.lower()
        self.text = text
        self.is_professional = is_professional
        self._id = _id 

    def get(self):
        assert db.name == 'recipes'
        assert (self.title and self.author) or self._id
        data = None
        if self.title and self.author:
            data = db.poems.find_one({'title': self.title, 'author': self.author})
        elif self._id:
            data = db.poems.find_one({'_id': self._id})
        if data:
            self.title = data['title']
            self.author = data['author']
            self.text = data['text']
            self.is_professional = data['professional']
            self._id = data['_id']

    def _is_duplicate(self):
        data = db.poems.find_one({'title': self.title, 'author': self.author})
        return data != None

    def save(self):
        assert db.name == 'recipes'
        assert self.title and self.author and self.text
        data = {'title': self.title, 
                'author': self.author,
                'text': self.text,
                'professional': self.is_professional}
        if self._id:
            db.poems.update({'_id': self._id}, data)
        elif not self._is_duplicate():
            self._id = db.poems.insert(data)
        return self._id


class Adjective:

    def __init__(self, word='', _id=None):
        assert type(word) is str or type(word) is unicode
        self.word = word.lower()
        self.synonyms = []
        self._id = _id

    def get(self):
        assert db.name == 'recipes'
        data = None
        if self._id:
            data = db.adjectives.find_one({'_id': self._id})
        else:
            data = db.adjectives.find_one({'word': self.word})
        if data:
            self._id = data['_id']
            self.synonyms = data['synonyms']

    def add_synonyms(self, synonyms):
        assert type(synonyms) is list or type(synonyms) is set
        self.synonyms = list(set(self.synonyms) | set(synonyms))

    def save(self):
        assert db.name == 'recipes'
        data = {'word': self.word, 'synonyms': self.synonyms}
        if self._id:
            data['_id'] = self._id
            db.adjectives.update({'_id': self._id}, data)
            return self._id
        else:
            return db.adjectives.insert(data)


def get_ingredient_names(valid_only=True):
    global db_ingredients
    if len(db_ingredients) == 0:
        sarg = {'valid': True} if valid_only else {}
        for c in db.ingredients.find(sarg):
            db_ingredients.append(c['name'])
    return db_ingredients

real_ingredients = set(n.lower() for n in get_ingredient_names())

def extract_ingredients(messy_ingredients):
    global real_ingredients
    pure_ingredients = []
    for line in messy_ingredients:
        words = [w.lower() for w in line.split()]
        two_words = set(words[ind-1] +' '+ word for ind, word in enumerate(words) if ind > 0)
        pure = real_ingredients & two_words
        if not pure:
            pure = real_ingredients & set(words)
        if pure:
            pure_ingredients.append(pure.pop())
    return pure_ingredients


def query_edamam(q, count=100):
    recipes = []
    try:
        cred = 'app_id=' + config['edamam_id'] + '&app_key=' + config['edamam_key']
        r_string = "https://api.edamam.com/search?{}&{}&{}".format("q=" + q, cred, "to=" + str(count))
        r = requests.get(r_string)
        for h in r.json()['hits']:
            name = h['recipe']['label']
            ingredients = [i['food'] for i in h['recipe']['ingredients']]
            url = h['recipe']['url']
            source = 'edamam'
            recipe = Recipe(name, ingredients, url, source)
            recipes.append(recipe)
    except e as Exception:
        print 'edamam error', e
        traceback.print_exc()
    finally:
        return recipes


def query_food2fork(q, skip_urls={}):
    key = 'key=' + config['food2fork_key']
    page = 1
    more = True
    recipes = []
    try:
        while more:
            get_string = "http://food2fork.com/api/search?{}&{}&{}".format("q=" + q,"page=" + str(page), key)
            resp = requests.get(get_string)
            page += 1
            more = resp.json()['count'] == 30 and resp.status_code == 200
            for r in resp.json()['recipes']:
                if r['source_url'] not in skip_urls:
                    get_string = "http://food2fork.com/api/get?rId={}&{}".format(r['recipe_id'], key)
                    resp2 = requests.get(get_string)
                    data = resp2.json()
                    name = data['recipe']['title']
                    ingredients = extract_ingredients(data['recipe']['ingredients'])
                    url = data['recipe']['source_url']
                    source = 'food2fork'
                    recipe = Recipe(name, ingredients, url, source)
                    recipes.append(recipe)
    except e as Exception:
        print 'food2fork error', e
        traceback.print_exc()
    finally:
        return recipes


def query_yummly(q, ingredients):
    ingr_list = ingredients.split(',') if ingredients else []
    recipes = []    
    try:
        cred = '_app_id=' + config['yummly_id'] + '&_app_key=' + config['yummly_key']
        ingr_string = ('allowedIngredient[]=' + '&allowedIngredient[]='.join(ingr_list)) if ingr_list else ''
        text_sarg = 'q=' + q if q else ''
        r_string = "http://api.yummly.com/v1/api/recipes?{}&{}&{}".format(text_sarg, ingr_string, cred)
        r = requests.get(r_string)
        for m in r.json()['matches']:
            name = m['recipeName']
            print name
            ingredients = extract_ingredients(m['ingredients'])
            url = 'http://www.yummly.com/recipe/external/' + m['id']
            source = 'yummly'
            recipe = Recipe(name, ingredients, url, source)
            recipes.append(recipe)
    except e as Exception:
        print 'yummly error', e
        traceback.print_exc()
    finally:
        return recipes



def search(ingredients_csv, text_sarg, test=True, jsonify=False, limit=100):
    recipes = []
    count = 0
    if test:
        for r in db.recipes.find():
            count += 1
            if count < limit:
                recipes.append(Recipe(json=r))
    else:
        edamam_sarg = text_sarg+','+ingredients_csv if text_sarg and ingredients_csv \
                                                    else text_sarg or ingredients_csv
        food2fork_sarg = text_sarg+'+'+ingredients_csv if text_sarg and ingredients_csv \
                                                        else text_sarg or ingredients_csv
        recipes += query_edamam(edamam_sarg)
        recipes += query_food2fork(food2fork_sarg)
        recipes += query_yummly(text_sarg, ingredients_csv)
    for recipe in recipes:
        recipe.get_adjectives()
    if jsonify:
        recipes = [r.to_json() for r in recipes]
    return recipes


def sort_score_recipes(recipes):
    genres = get_genre_names()
    scored_recipes = []
    for recipe in recipes:
        sort_scores = {}
        genre_scores = recipe.get_genre_scores(genres)
        ingr_count = len(recipe.ingredients)
        for genre in genre_scores:
            sort_scores[genre] = sum(score for _, score in genre_scores[genre].items()) / ingr_count
        sort_scores['Silence'] = -sum(sort_scores.values())
        scored_recipes.append({'recipe': recipe.for_web(), 'sort_scores': sort_scores})
    return scored_recipes


def get_genre_names():
    return ['Rock', 'Jazz', 'Classical']
