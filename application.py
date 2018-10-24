import os
import requests

from flask import Flask, session, render_template, url_for, request, redirect, jsonify
from flask_session import Session
from sqlalchemy import create_engine
from sqlalchemy.orm import scoped_session, sessionmaker
from werkzeug.security import check_password_hash, generate_password_hash

app = Flask(__name__)

# Check for environment variable
if not os.getenv("DATABASE_URL"):
    raise RuntimeError("DATABASE_URL is not set")

# Configure session to use filesystem
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Set up database
engine = create_engine(os.getenv("DATABASE_URL"))
db = scoped_session(sessionmaker(bind=engine))

# setting up the main index
@app.route("/")
def index():
    return render_template("index.html")

# setting up the registration
@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "GET":
        # return register page
        return render_template("register.html")

    elif request.method == "POST":
        # error checking
        if not request.form.get("username"):
            return render_template("failure.html", error="Please enter username",code="403!")
        if not request.form.get("password"):
            return render_template("failure.html", error="Please enter password",code="403!")
        if not request.form.get("repassword"):
            return render_template("failure.html", error="Please confirm password", code="403!")
        if request.form.get("password") != request.form.get("repassword"):
            return render_template("failure.html", error="Please enter same passwords", code="403!")

        # hashing passwords
        hash = generate_password_hash(request.form.get("password"))

        #adding username to database
        #if result not created this means username already exists
        try:
            db.execute("INSERT INTO users (username,hash) VALUES (:username, :hash)",
            {"username": request.form.get("username"), "hash": hash})
        except ValueError:
            return render_template("failure.html", error="Username already exists", code="403!")

        # storing id in session    postgres://gjrfgfjfzgxsfp:2e4141a9aac17a7e2e577875a8f9fdb89ed96503f8bbb2e5b964ba3a750abba3@ec2-50-19-86-139.compute-1.amazonaws.com:5432/d3hpv6t8ebv36k
        rows = db.execute("SELECT * FROM users WHERE username = :username ",{"username": request.form.get("username")}).fetchall()
        session["user_id"] = rows[0]["id"]
        db.commit()

        # Redirect user to home page
        return redirect("/")

# setting up logout
@app.route("/logout")
def logout():
    """Log user out"""

    # Forget any user_id
    session.clear()

    # Redirect user to login form
    return redirect("/")

# setting up login
@app.route("/login", methods=["GET", "POST"])
def login():

    # Forget any user_id
    session.clear()

    # User reached route via POST
    if request.method == "POST":

        # Ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username", 403)

        # Ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password", 403)

        # Query database for username
        rowsc = db.execute("SELECT * FROM users WHERE username = :username",
        {"username":request.form.get("username")}).rowcount
        rows = db.execute("SELECT * FROM users WHERE username = :username", {"username":request.form.get("username")}).fetchall()
        db.commit()

        # Ensure username exists and password is correct
        if rowsc != 1 or not check_password_hash(rows[0]["hash"], request.form.get("password")):
            return render_template("failure.html",error="Wrong Username/Password Combination", code="403!")

        # Remember which user has logged in
        session["user_id"] = rows[0]["id"]

        # Redirect user to home page
        return redirect("/")

        # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("login.html")

# setting up the search backend
@app.route("/search", methods=["GET", "POST"])
def search():
    if request.method == "POST":

        # getting the Query
        query = request.form.get("query")

        # error check
        if not query:
            return render_template("failure.html", error="Please enter some query", code = "403!")

        # adding search abilities
        query = query + "%"

        # getting respective rows from database
        books = db.execute("SELECT * FROM books WHERE (isbn ILIKE :query) OR (title ILIKE :query) OR (author ILIKE :query)",
        {"query":query}).fetchall()
        db.commit()

        # making returning of data safe
        if len(books) > 10:
            books = books[:10]

        if not books:
            return render_template("failure.html", error="No Results", code ="OOPS!")

        #rendering to website
        return render_template("search.html", books = books)

    elif request.method == "GET":
        return render_template("index.html")

# setting up book passenger
@app.route("/<isbn>", methods=["GET", "POST"])
def book(isbn):
    if request.method == "GET":

        # getting the book from database
        book = db.execute("SELECT * FROM books WHERE isbn=:isbn", {"isbn": isbn}).fetchone()
        if book is None:
            return render_template("failure.html", error="Please enter some query", code = "403!")

        # getting review if any
        reviews = db.execute("SELECT * FROM reviews WHERE isbn =:isbn",{"isbn":isbn}).fetchall()
        db.commit()

        #api access
        res = requests.get("https://www.goodreads.com/book/review_counts.json", params={"key": "TD5UDFfKB6QfUsk8sqRXw", "isbns": isbn})
        average_rating = res.json()['books'][0]['average_rating']
        number_rating = res.json()['books'][0]['work_ratings_count']

        # giving details to webpage
        return render_template("book.html",res1 = average_rating ,res2 = number_rating, book = book, reviews= reviews)

    elif request.method == "POST":
        book = db.execute("SELECT * FROM books WHERE isbn=:isbn", {"isbn": isbn}).fetchone()
        reviews = db.execute("SELECT * FROM reviews WHERE isbn =:isbn",{"isbn":isbn}).fetchall()

        #checking if review is there
        getreview = request.form.get("review")
        if not getreview:
            return render_template("failure.html", error="Please write review", code = "403!")

        getrate = request.form.get("rate")
        if not getrate:
            return render_template("failure.html", error="Please rate", code = "403!")

        #error check if user has added review already
        getid = session["user_id"]
        checkreview = db.execute("SELECT * FROM reviews WHERE isbn=:isbn AND userid=:userid",
        {"isbn":isbn, "userid": getid}).fetchone()

        if checkreview:
            return render_template("failure.html", error="You cannot review more than once for one book", code = "403!")

        elif not checkreview:
            db.execute("INSERT INTO reviews (review,isbn, rate, userid) VALUES (:review, :isbn, :rate, :userid)",
            {"review":getreview,  "isbn":isbn, "rate":getrate, "userid":getid})
        db.commit()

        return render_template("book.html", book = book, reviews = reviews)

@app.route("/api/<isbn>")
def book_api(isbn):
    # getting the book from database
    book = db.execute("SELECT * FROM books WHERE isbn=:isbn", {"isbn": isbn}).fetchone()
    #api access
    res = requests.get("https://www.goodreads.com/book/review_counts.json", params={"key": "TD5UDFfKB6QfUsk8sqRXw", "isbns": isbn})
    reviews_count = res.json()['books'][0]['reviews_count']
    average_rating = res.json()['books'][0]['average_rating']

    return jsonify({
        "title": book.title,
        "author": book.author,
        "year": book.year,
        "isbn": isbn,
        "review_count": reviews_count,
        "average_score": average_rating
    })
