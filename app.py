import os

from cs50 import SQL
from flask import Flask, flash, redirect, render_template, request, session
from flask_session import Session
from tempfile import mkdtemp
from werkzeug.security import check_password_hash, generate_password_hash


from helpers import apology, login_required, lookup, usd

# Configure application
app = Flask(__name__)

# Ensure templates are auto-reloaded
app.config["TEMPLATES_AUTO_RELOAD"] = True

# Custom filter
app.jinja_env.filters["usd"] = usd

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Configure CS50 Library to use SQLite database
db = SQL("sqlite:///finance.db")

# Make sure API key is set
if not os.environ.get("API_KEY"):
    raise RuntimeError("API_KEY not set")


@app.after_request
def after_request(response):
    """Ensure responses aren't cached"""
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response


@app.route("/")
@login_required
def index():
    """Show portfolio of stocks"""

    #loads users porfolio
    portfolio = db.execute("SELECT symbol, name, shares, aprice, tot_price FROM portfolio WHERE user_id = :user_id", user_id=session["user_id"])


    #check if user owns any stocks
    if len(portfolio) != 0:
        #getting user dispenpel cash
        cash = db.execute("SELECT cash FROM users WHERE id = :id", id=session["user_id"])

        #getting total of value and getting currect info on stock
        current_price = []
        tot_stock_worth_list = []
        nr_stocks = len(portfolio)

        tot_stock_worth = 0
        for nr in range(len(portfolio)):
            stock = portfolio[nr].get("symbol")
            shares = portfolio[nr].get("shares")
            stock_worth = lookup(stock)
            stock_worth = stock_worth.get("price")
            tot_stock_worth = shares * stock_worth

            #adds price to list to print for idividualstock
            current_cash = cash[0].get("cash")
            print("!!!!--",current_cash)
            current_price.append(stock_worth)
            tot_stock_worth_temp = usd(tot_stock_worth)
            tot_stock_worth_list.append(tot_stock_worth_temp)


        tot_worth = tot_stock_worth + cash[0].get("cash")
        # -- need to get name and currenct price from stock --
        tot_usd = usd(tot_worth)


        return render_template("index.html", portfolio=portfolio, tot_usd=tot_usd, current_price=current_price, tot_stock_worth_list=tot_stock_worth_list, nr_stocks=nr_stocks, current_cash=current_cash)
    #load stock-less page
    else:
        return render_template("index_nostocks.html")




@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    """Buy shares of stock"""

    #Loading cash of currect user from db
    cash = db.execute("SELECT cash FROM users WHERE id = :id", id=session["user_id"])

    #converts list and dict to cash
    cash = cash[0].get('cash')

    #if stocks is trying to be bought
    if request.method == "POST":
        ticket = request.form.get("symbol")
        result = lookup(ticket)
        shares = request.form.get("shares")
        #check for positive value on amount of shares
        if shares.isdigit() == False:
            return apology("Only positiv amount possible")
        elif result == None:
            return apology("No results found search again")

        #check if user can afford
        aprice = result["price"]
        amount = int(shares) * aprice

        if amount > cash:
            return apology("You cant afford this")

        else:
            cash -= amount
            #updates users wallet
            db.execute("UPDATE users SET cash = :cash WHERE id = :id", cash=cash, id=session["user_id"])
            #save the transaction to db
            
            db.execute("INSERT INTO transactions (user_id, symbol, shares, aprice, tot_price, transtype) VALUES(?, ?, ?, ?, ?, ?)", session["user_id"], result["symbol"], shares, aprice, amount,"BUY")
            #update users portfolio
            #checks if user owns stock already
            stocks_ownd = db.execute("SELECT symbol FROM portfolio WHERE user_id = ?", session["user_id"])
            #if result["symbol"] is stocks:
            first_stock_status = True
            for stock in stocks_ownd:
                if result["symbol"] == stock["symbol"]:

                    #add up total amount of shares of the stock
                    port_shares_n_price = db.execute("SELECT shares, tot_price FROM portfolio WHERE user_id = ? AND symbol = ?", session["user_id"], stock["symbol"])
                    port_shares_n_price = port_shares_n_price[0]
                    current_shares = port_shares_n_price["shares"]

                    #getting varibles for the New total amount of shares and New total mean price
                    new_tot_shares = int(shares) + current_shares
                    new_tot_price = (float(port_shares_n_price["tot_price"]) + amount) / new_tot_shares

                    db.execute("UPDATE portfolio SET shares = :shares, tot_price =:new_tot_price WHERE user_id = :userid AND symbol = :symbol", shares=new_tot_shares, new_tot_price=new_tot_price, userid=session["user_id"], symbol=stock["symbol"])

                    #changes status on the stock so it does add twice
                    first_stock_status = False

            #if user doest have stock already make entery
            if first_stock_status == True:

                db.execute("INSERT INTO portfolio (user_id, symbol, shares, aprice, tot_price, name) VALUES(?, ?, ?, ?, ?, ?)", session["user_id"], result["symbol"], shares, aprice, amount, result["name"])


            return redirect("/")




    #landing in /buy showing current amount of money
    else:
        return render_template("buy.html", cash=cash)

    return apology("Something went wrong :S")


@app.route("/history")
@login_required
def history():
    """Show history of transactions"""
    #Get users transaction history
    transactions = db.execute("SELECT * FROM transactions WHERE user_id = :user_id", user_id=session["user_id"])

    #Check if user has a history else return error
    if len(transactions) > 0:
        print("transactions:", transactions, len(transactions))
        return render_template("history.html", transactions=transactions)

    return apology("You dont have any history yet")


@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in"""

    # Forget any user_id
    session.clear()

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # Ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username", 403)

        # Ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password", 403)

        # Query database for username
        rows = db.execute("SELECT * FROM users WHERE username = ?", request.form.get("username"))

        # Ensure username exists and password is correct
        if len(rows) != 1 or not check_password_hash(rows[0]["hash"], request.form.get("password")):
            return apology("invalid username and/or password", 403)

        # Remember which user has logged in
        session["user_id"] = rows[0]["id"]

        # Redirect user to home page
        return redirect("/")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("login.html")


@app.route("/logout")
def logout():
    """Log user out"""

    # Forget any user_id
    session.clear()

    # Redirect user to login form
    return redirect("/")


@app.route("/quote", methods=["GET", "POST"])
@login_required
def quote():
    """Get stock quote."""
    if request.method == "POST":

        symbol = request.form.get("symbol")
        #check for not empty search
        if symbol is not None:
            result = lookup(symbol)
            #checks if anything is found else return fault
            if result is not None:
                return render_template("/quoted.html", result=result)

            else:
                return apology("Please input a valid ticker")

        else:
            return apology("Please input a ticker")

    else:
        return render_template("/quote.html")




@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user"""
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")
        veripass = request.form.get("confirmation")

        #username check, checks if username if found in db and if empty
        check_username = db.execute("SELECT username FROM users WHERE username = :username", username=username)
        if check_username:
            return apology("Username is already taken")
        elif len(username) < 1:
            return apology("Username most contain letters")

        #password check
        if len(password) < 1:
            return apology("The password most be longer")
        elif password != veripass:
            return apology("The password doest match")

        #checks completed/register user with hashed pw
        hash = generate_password_hash(password)
        db.execute("INSERT INTO users (username, hash) VALUES(?, ?)", username, hash)

        #Saves the user ID as session user. Then logs-in user and redirects
        get_id = db.execute("SELECT id FROM users WHERE username = :username", username=username)

        get_id = get_id[0]
        session["user_id"] = get_id['id']
        return redirect("/")

    else:
        #users = db.execute("SELECT * FROM users")
        return render_template("/register.html")

@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    """Sell shares of stock"""
    #First check if user has stocks to sell / else user get error code
    portfolio = db.execute("SELECT symbol, name, shares, aprice, tot_price FROM portfolio WHERE user_id = :user_id", user_id=session["user_id"])
    if len(portfolio) != 0:

        #When user trying to sell a stock
        if request.method == "POST":
            #Check if user has that amount of stocks or wrong input
            sell_symbol = request.form.get("symbol")
            sell_shares = int(request.form.get("shares"))
            #Get data about currently owned holdings
            owned = db.execute("SELECT shares, tot_price FROM portfolio WHERE user_id = :user_id AND symbol = :symbol", user_id=session["user_id"], symbol=sell_symbol)
            owned_shares = owned[0].get("shares")
            owned_tot_price = owned[0].get("tot_price")
            #Look up current stockprice and worth of the sell
            current = lookup(sell_symbol)
            current_price = current.get("price")
            sell_worth = current_price * sell_shares

            #If user Sell is OK!
            if sell_shares > 0 and sell_shares <= owned_shares:

                #loads current cash
                cash = db.execute("SELECT cash FROM users WHERE id = :id", id=session["user_id"])

                #Saves the sell transaction
                db.execute("INSERT INTO transactions (user_id, symbol, shares, aprice, tot_price, transtype) VALUES(?, ?, ?, ?, ?, ?)", session["user_id"], sell_symbol, sell_shares, current_price, sell_worth,"SELL")

                #Calculates the new total sell price and new total cash
                updated_shares = owned_shares - sell_shares
                cash = cash[0].get("cash") + sell_worth

                #Removes the sold shares from portfolio
                #if shares now is 0 remove entier stock else just update and add sell worth to cash
                if updated_shares > 0:
                    #updates new price and nr of shares for stock
                    new_tot_price = (float(owned_tot_price) - sell_worth) / updated_shares
                    db.execute("UPDATE portfolio SET shares = :shares, tot_price =:new_tot_price WHERE user_id = :userid AND symbol = :symbol", shares=updated_shares, new_tot_price=new_tot_price, userid=session["user_id"], symbol=sell_symbol)
                    #----add money back to cash----
                    db.execute("UPDATE users SET cash = :cash WHERE id = :id", cash=cash, id=session["user_id"])
                    return redirect("/")
                else:
                    #Delete Stock row from portolio
                    db.execute("DELETE FROM portfolio WHERE user_id = :userid AND symbol = :symbol", userid=session["user_id"], symbol=sell_symbol)
                    #add money back to cash
                    db.execute("UPDATE users SET cash = :cash WHERE id = :id", cash=cash, id=session["user_id"])
                    return redirect("/")

            else:
                return apology("You dont have that many shares to sell or wrong input")

        else:
            return render_template("sell.html", portfolio=portfolio)


    return apology("You have no stocks to sell")

@app.route("/deposit", methods=["GET", "POST"])
@login_required
def deposit():
    """Own function for user to make a deposit"""

    #If deposit is trying to be made(post)
    if request.method == "POST":
        #Get currenct amount of cash
        cash = db.execute("SELECT cash FROM users WHERE id = :id", id=session["user_id"])
        deposit = request.form.get("deposit")

        #Check if input is correct
        if deposit.isnumeric() == True and int(deposit) > 0:
            cash = cash[0].get("cash") + int(deposit)
            db.execute("UPDATE users SET cash = :cash WHERE id = :id", cash=cash, id=session["user_id"])
            return redirect("/")
        else:
            return apology("Wrong input")

    #get the page(get)
    else:
        return render_template("deposit.html")
