import os
import json
import time
import random
import smtplib
import re
import string
import requests
import pandas as pd
import matplotlib.pyplot as plt
from flask import Flask, render_template, request, redirect, url_for, session, send_file
from better_profanity import profanity
from werkzeug.security import generate_password_hash, check_password_hash
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import nltk
from nltk.corpus import stopwords
from nltk.stem.porter import PorterStemmer

UPLOAD_FOLDER = 'static/file/'
app = Flask(__name__)
app.secret_key = os.urandom(24)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

user_data_file = 'users.json'
tweets_file = 'tweets.json'
otp_store = {}
vulgar_words_count = {}

# -------------------- Helpers -------------------- #
def load_users():
    return json.load(open(user_data_file)) if os.path.exists(user_data_file) else {}

def save_users(users):
    with open(user_data_file, 'w') as f:
        json.dump(users, f)

def load_tweets():
    return json.load(open(tweets_file)) if os.path.exists(tweets_file) else []

def save_tweets(tweets):
    with open(tweets_file, 'w') as f:
        json.dump(tweets, f)

def send_email(to_email, subject, body):
    sender_email = 'asikamani29@gmail.com'
    sender_pass = 'cfrf yvxw gucz ippy'
    msg = MIMEMultipart()
    msg['From'] = sender_email
    msg['To'] = to_email
    msg['Subject'] = subject
    msg.attach(MIMEText(body, 'plain'))

    try:
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(sender_email, sender_pass)
        server.sendmail(sender_email, to_email, msg.as_string())
        server.quit()
        print(f"📧 Email sent to {to_email}")
    except Exception as e:
        print("❌ Email failed:", e)

def send_otp_email(email, otp):
    subject = 'Your OTP Code'
    body = f'Your OTP is: {otp}'
    send_email(email, subject, body)

def get_client_ip():
    if request.headers.getlist("X-Forwarded-For"):
        ip = request.headers.getlist("X-Forwarded-For")[0].split(',')[0]
    else:
        ip = request.remote_addr
    return ip

def send_login_notification(email, ip):
    try:
        res = requests.get(f'http://ip-api.com/json/{ip}').json()
        city = res.get('city', 'Unknown')
        region = res.get('regionName', '')
        country = res.get('country', '')
        location_parts = [part for part in [city, region, country] if part]
        location = ', '.join(location_parts) if location_parts else "Unknown"
    except Exception:
        location = "Unknown"
    subject = "Login Detected"
    body = f"""Login detected for your account:

IP Address: {ip}
Location: {location}

If this wasn’t you, please secure your account immediately."""
    send_email(email, subject, body)

# -------------------- Routes -------------------- #
@app.route('/')
def login():
    return render_template('login.html')

@app.route('/login', methods=['POST'])
def user_login():
    name = request.form.get('name')
    password = request.form.get('password')
    users = load_users()

    if name in users:
        if users[name].get('banned'):
            return render_template('login.html', msg='Your account has been banned.')
        if not users[name].get('verified'):
            return render_template('login.html', msg='Account not verified.')
        if check_password_hash(users[name]['password'], password):
            session['uname'] = name
            ip = get_client_ip()
            send_login_notification(name, ip)
            return redirect(url_for('twitter'))
    return render_template('login.html', msg='Invalid credentials.')

@app.route('/NewUser')
def newuser():
    return render_template('NewUser2.html')

@app.route('/reg', methods=['POST'])
def register():
    name = request.form.get('email')
    fname = request.form.get('first_name')
    dob = request.form.get('dob')
    password = request.form.get('password')

    if not name or '@' not in name:
        return render_template('NewUser2.html', msg='Enter a valid email address.')

    users = load_users()
    if name in users:
        return render_template('NewUser2.html', msg='User already exists.')

    otp = str(random.randint(100000, 999999))
    otp_store[name] = {'fname': fname, 'dob': dob, 'password': password, 'otp': otp}
    send_otp_email(name, otp)
    session['pending_email'] = name
    return render_template('otp_verify.html', email=name)

@app.route('/verify_otp', methods=['POST'])
def verify_otp():
    email = request.form.get('email')
    input_otp = request.form.get('otp')
    users = load_users()

    if email in otp_store and otp_store[email]['otp'] == input_otp:
        hashed = generate_password_hash(otp_store[email]['password'])
        users[email] = {
            'fname': otp_store[email]['fname'],
            'dob': otp_store[email]['dob'],
            'password': hashed,
            'banned': False,
            'verified': True
        }
        save_users(users)
        otp_store.pop(email)
        session.pop('pending_email', None)
        return render_template('login.html', msg='Account verified & registered.')
    return render_template('otp_verify.html', msg='Invalid OTP', email=email)

@app.route('/about')
def about():
    return render_template('about.html')

@app.route('/twitter')
def twitter():
    uname = session.get('uname')
    if not uname:
        return redirect(url_for('login'))

    if session.get("final_ban"):
        session.pop("final_ban")
        return render_template('twitter.html', view='style=display:block', value='You have been permanently banned.')
    
    return render_template('twitter.html', view='display:none', value='')

@app.route('/send', methods=['POST'])
def send():
    global vulgar_words_count
    username = session.get('uname')
    if not username:
        return redirect(url_for('login'))

    users = load_users()
    if users.get(username, {}).get('banned'):
        return render_template('twitter.html', view='style=display:block', value='You are banned.')

    msg = request.form.get('msg')
    censored = profanity.censor(msg)

    if '*' in censored:
        vulgar_words_count[username] = vulgar_words_count.get(username, 0) + 1
        count = vulgar_words_count[username]
        if count >= 3:
            users[username]['banned'] = True
            save_users(users)
            session["final_ban"] = True
            return redirect(url_for('twitter'))
        return render_template('twitter.html', view='style=display:block', value=f'Profanity warning #{count}')
    
    tweets = load_tweets()
    tweets.append({'name': username, 'date': time.time(), 'tweet': msg})
    save_tweets(tweets)
    return render_template('twitter.html', view='style=display:block', value='Tweet posted.')

@app.route('/tweet')
def tweet():
    tweets = load_tweets()
    return render_template('tweet.html', data=tweets or None, msg='No tweets yet' if not tweets else '')

@app.route('/upload.html')
def up():
    return render_template('upload.html')

@app.route('/upload', methods=['POST'])
def upload():
    global df
    for file in ['perform.png', 'abc.png', 'dtc.png', 'gnb.png', 'lgr.png', 'rfc.png']:
        path = os.path.join(app.config['UPLOAD_FOLDER'], file)
        if os.path.exists(path):
            os.remove(path)

    file1 = request.files['jsonfile']
    jsonfile = os.path.join(app.config['UPLOAD_FOLDER'], file1.filename) if file1 else 'static/file/Dataset.json'
    if file1:
        file1.save(jsonfile)

    df = pd.read_json(jsonfile)
    df['annotation'] = df['annotation'].apply(lambda x: 1 if x['label'][0] == '1' else 0)
    df.drop(['extras'], axis=1, inplace=True)
    df['annotation'].value_counts().sort_index().plot.bar()
    plt.savefig('static/file/perform.png')

    nltk.download('stopwords')
    stop = stopwords.words('english')
    regex = re.compile('[%s]' % re.escape(string.punctuation))
    df['cleaned'] = df['content'].apply(lambda x: ' '.join([w for w in x.split() if w.lower() not in stop]))
    df['cleaned'] = df['cleaned'].apply(lambda x: regex.sub('', x))

    porter = PorterStemmer()
    nltk.download('punkt')
    df['final_text'] = df['cleaned'].apply(lambda x: [porter.stem(w) for w in nltk.word_tokenize(x)])

    df.to_json('static/file/output.json')
    return render_template('select.html')

@app.route('/download')
def download():
    return send_file('static/file/output.json', as_attachment=True)

@app.route('/delete_account/<username>')
def delete_account(username):
    users = load_users()
    users.pop(username, None)
    save_users(users)
    return redirect(url_for('login'))

if __name__ == '__main__':
    app.run(debug=True)
