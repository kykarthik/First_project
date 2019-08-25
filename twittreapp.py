from datetime import datetime, date
from email.message import EmailMessage
from email.utils import make_msgid
from email import encoders
from flask import Flask, render_template, request, session, redirect, url_for, flash, Markup
from celery_config import make_celery
import smtplib
import tweepy

app = Flask(__name__)
app.secret_key = b'_5#y2L"F4Q8z\n\xec]/'
current_year = date.today().year
own_list = []
others_list = []
app.config['CELERY_BROKER_URL'] = 'amqp://localhost//'

celery = make_celery(app)

def authenticate():
	auth = tweepy.OAuthHandler(session.get('consumer_key'), session.get('consumer_secret'))
	auth.set_access_token(session.get('access_token'), session.get('access_token_secret'))
	api = tweepy.API(auth)
	return api

@celery.task(name='twitterapp.send_mail')
def send_mail(tweet, date_time, from_mail, password, to_mail):
	try:
		from_email = from_mail
		password = password
		to_emails = to_mail
		server = smtplib.SMTP('smtp.office365.com' , 587)
		server.starttls()
		server.login(from_email, password)
		msg = EmailMessage()
		msg['From'] = from_email
		msg['To'] = to_emails
		msg['Subject'] = "New Tweet post update"
		text = "<strong>" + session.get('user_name') + " posted a new tweet on  " + str(date_time) + "</strong><br>" + "<i>" + "&ensp;&ensp;&ensp;" + tweet + "</i>"
		msg.add_alternative(text, subtype='html')
		server.send_message(msg, from_email, to_emails.split(','))
		print("Mail Sent")
		server.quit()
	except Exception as e:
		return False

def get_all_tweets(api, screen_name):
	user = api.me()
	if user.screen_name == screen_name:
		my_values = own_list
	else:
		my_values = others_list
	my_values.clear()
	months = [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0]
	alltweets = []	
	new_tweets = api.user_timeline(screen_name=screen_name, count=200)
	alltweets.extend(new_tweets)
	oldest = alltweets[-1].id - 1
	while len(new_tweets) > 0:
		new_tweets = api.user_timeline(screen_name = screen_name, count=200, max_id=oldest)
		alltweets.extend(new_tweets)
		oldest = alltweets[-1].id - 1

	for item in alltweets:
		month = item.created_at.month
		year = item.created_at.year
		if year < current_year:
			continue
		else:
			new_val = months[month]
			months[month] = new_val + 1

	my_values.extend(months[1:])


@app.route('/')
def index():
	return render_template('twitter_index.html')

@app.route('/get_others_activity', methods=['GET', 'POST'])
def get_others_activity():
	api = authenticate()
	legend = 'Monthly Data'
	labels = ("January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December")
	other_user = request.form['usernames']
	if request.method == 'POST':
		get_all_tweets(api, other_user)
		return render_template('welcome.html', values=others_list, labels=labels, legend=legend,user_name=other_user)
	else:
		return render_template('welcome.html', values=others_list, labels=labels, legend=legend,user_name=other_user)

@app.route('/handle_data', methods=['GET','POST'])
def handle_data():
	legend = 'Monthly Data'
	labels = ("January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December")
	if request.method == 'POST':
		session['consumer_key'] = request.form['consumer_key']
		session['consumer_secret'] = request.form['consumer_secret']
		session['access_token'] = request.form['access_token']
		session['access_token_secret'] = request.form['access_token_secret']
		try:
			api = authenticate()
			user = api.me()
			session['user_name'] = user.name
			session['user_screen_name'] = user.screen_name
			get_all_tweets(api, session.get('user_screen_name'))
			api.verify_credentials()
			flash('Authentication Successful', 'success')
			return render_template('welcome.html', values=own_list, labels=labels, legend=legend, user_name=session.get('user_name'))
		except tweepy.TweepError as e:
			flash(e.args[0][0]['message'], 'error')
			return render_template('twitter_index.html')
	else:
		return render_template('welcome.html', values=own_list, labels=labels, legend=legend, user_name=session.get('user_name'))

@app.route('/tweet_post', methods=['GET', 'POST'])
def tweet_post():
	if request.method == 'POST':
		my_tweet = request.form['description']
		api = authenticate()
		try:
			tweet = api.update_status(my_tweet)
			flash('Successfully posted the tweet', 'success')
			radio = False
			if request.form.get('mail_sender'):
				radio = True
			if(radio):
				from_mail = request.form['from_mail']
				password = request.form['password']
				to_mail = request.form['to_mail']
				date_time = tweet.created_at
				send_mail.delay(my_tweet, date_time, from_mail, password, to_mail)
				# result = send_mail(tweet, date_time, from_mail, password, to_mail)
				# if(result):
				# 	flash('Mail sent Successfully', 'success')
				# else:
				# 	flash('Mail sent UnSuccessfull', 'error')
		except tweepy.TweepError as e:
			flash(e.args[0][0]['message'], 'error')
			return redirect(url_for('tweet_post'))
	return render_template('post_tweet.html')

@app.route('/profile')
def profile():
	api = authenticate()
	user = api.me()
	user_name = user.name
	user_screen_name = user.screen_name
	user_location = user.location
	user_friend_count = user.friends_count
	followers_count = user.followers_count
	profile_image = user.profile_image_url
	status_posted = user.statuses_count
	return render_template('profile.html', user_name=user_name, screen_name=user_screen_name, location=user_location, friend_count=user_friend_count, followers_count=followers_count, profile_image=profile_image, status_posted=status_posted)

@app.route('/get_tweets', methods=['GET', 'POST'])
def get_tweets():
	tweets = {}
	if request.method == 'POST':
		user = request.form['get_tweets']
		users = user.split(',')
		api = authenticate()
		try:
			for celebs in users:
				tweet_list = []
				my_list = []
				person = api.get_user(celebs)
				tweet_list = api.user_timeline(screen_name= celebs,
											count=10,
											include_rts = False,
											tweet_mode = 'extended')
				for info in tweet_list:
					tweet_with_date = {}
					tweet_with_date[str(info.created_at)] = info.full_text
					my_list.append(tweet_with_date)
				tweets[person.name] = my_list
			return render_template('get_tweet.html', tweets=tweets)
		except tweepy.TweepError as e:
			flash(e.args[0][0]['message'], 'error')
			return redirect(url_for('get_tweets', tweets=tweets))
	else:
		return render_template('get_tweet.html', tweets=tweets)


@app.route('/message', methods=['GET', 'POST'])
def message():
	if request.method == 'POST':
		user = request.form['reciever']
		msg_content = request.form['msg']
		api = authenticate()
		try:
			if api.send_direct_message(user, msg_content):
				flash('Message sent Successfully', 'success')
				return redirect(url_for('message'))
			else:
				flash('Could not send the message', 'error')
		except tweepy.TweepError as e:
			flash(e.args[0][0]['message'], 'error')
			return redirect(url_for('message'))
	else:
		return render_template('send_message.html')

@app.route('/follow', methods=['GET', 'POST'])
def follow():
	if request.method == 'POST':
		user = request.form['follow_name']
		api = authenticate()
		try:
			if api.create_friendship(user):
				flash('Now you are following ' + user, 'success' )
				return redirect(url_for('follow'))
			else:
				flash('Unable to follow ' + user, 'error')
				return redirect(url_for('follow'))
		except tweepy.TweepError as e:
			flash(e.args[0][0]['message'], 'error')
			return redirect(url_for('follow'))
	else:
		return render_template('follow_someone.html')

@app.route('/block', methods=['GET', 'POST'])
def block():
	if request.method == 'POST':
		user = request.form['block_name']
		checkbox = False
		if request.form.get('chbox'):
			checkbox = True
		api = authenticate()
		try:
			if (checkbox):
				if api.destroy_block(user):
					flash('You Unblocked ' + user, 'success' )
					return redirect(url_for('block'))
				else:
					flash('Unable to Unblock ' + user, 'error')
					return redirect(url_for('block'))
			else:
				if api.create_block(user):
					flash('You blocked ' + user, 'success' )
					return redirect(url_for('block'))
				else:
					flash('Unable to block ' + user, 'error')
					return redirect(url_for('block'))

		except tweepy.TweepError as e:
			flash(e.args[0][0]['message'], 'error')
			return redirect(url_for('block'))
	else:
		return render_template('block_or_unblock.html')


if __name__ == '__main__':
	app.run(debug=True)
