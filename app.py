__author__ = 'jperelshteyn'

from flask import Flask, render_template, request, redirect, url_for, abort, session

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

if __name__ == '__main__':
    app.run()