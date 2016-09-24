import tweepy
import pifacecad
from datetime import datetime
from dateutil import tz
from time import sleep
import threading
from twitterkey import *
from random import randint

# Setup the PiFace screen, clearing it and hiding the cursor
cad = pifacecad.PiFaceCAD()
cad.lcd.backlight_on()
cad.lcd.clear()
cad.lcd.cursor_off()
cad.lcd.blink_off()

# Create the custom characters for our animations
# As the characters are very thin, designs are spread over two characters
# Unfortunately can only store 8 chars :(
# Characters designed with this handy tool: http://www.quinapalus.com/hd44780udg.html

# The coffee cup
cupBM1 = pifacecad.LCDBitmap([
	0x0,0xf,0x1f,0x17,0x10,0x10,0x8,0x7
	])
cad.lcd.store_custom_bitmap(0,cupBM1)
cupBM2 = pifacecad.LCDBitmap([
	0x0,0x10,0x1e,0x15,0x5,0x6,0x8,0x10
	])
cad.lcd.store_custom_bitmap(1,cupBM2)

# Full steam frame (two frames of animation)
steam1BM1 = pifacecad.LCDBitmap([
	0x9,0x9,0x12,0x12,0x9,0x9,0x0,0x0
	])
cad.lcd.store_custom_bitmap(2,steam1BM1)
steam1BM2 = pifacecad.LCDBitmap([
	0x12,0x12,0x9,0x9,0x12,0x12,0x0,0x0
	])
cad.lcd.store_custom_bitmap(3,steam1BM2)

# Less steam (two frames of animation)
steam2BM1 = pifacecad.LCDBitmap([
	0x4,0x4,0x8,0x8,0x4,0x4,0x0,0x0
	])
cad.lcd.store_custom_bitmap(4,steam2BM1)
steam2BM2 = pifacecad.LCDBitmap([
	0x4,0x4,0x2,0x2,0x4,0x4,0x0,0x0
	])
cad.lcd.store_custom_bitmap(5,steam2BM2)

# 'Flies' over two frames
fliesBM1 = pifacecad.LCDBitmap([
	0x0,0x0,0x10,0x2,0x0,0x8,0x0,0x0
	])
cad.lcd.store_custom_bitmap(6,fliesBM1)
fliesBM2 = pifacecad.LCDBitmap([
	0x0,0x0,0x2,0x0,0x8,0x0,0x4,0x0
	])
cad.lcd.store_custom_bitmap(7,fliesBM2)

lock = threading.Lock()
lastTime = datetime.now()
timeFactor = 5
from_zone = tz.gettz("GMT")
to_zone = tz.tzlocal()
steamState = 0

# Run an animation according to the state of the coffee
# Danger: Infinite loop!
def SteamThread():
	global timeFactor
	global lastTime
	global steamState
	lock.acquire()
        waitTime = 15.0
        
        if timeFactor >= 60:
                # If 90 mins or older, show flies over the coffee
                if timeFactor >= 90:
                	cad.lcd.set_cursor(0,0)
                	cad.lcd.write_custom_bitmap(randint(6,7))
                        cad.lcd.write_custom_bitmap(randint(6,7))
                        waitTime = 1

                # If an hour or older, show no steam (went cold)
                else:
                        cad.lcd.set_cursor(0,0)
                        cad.lcd.write("  ")
                        
                lock.release()
                t = threading.Timer(waitTime, SteamThread)
                t.daemon = True
                t.start()
        else:
                # Show less steam after 15 mins
                bmp = 2
                if timeFactor > 15:
                        bmp = 4

                # Sleep controls animation speed
                # Steam moves faster the fresher the coffee
                # Capped at 5 fps

                if steamState == 0:
                        cad.lcd.set_cursor(0,0)
                        cad.lcd.write_custom_bitmap(bmp)
                        cad.lcd.write_custom_bitmap(bmp)
                        steamState = 1
                else:
                        cad.lcd.set_cursor(0,0)
                        cad.lcd.write_custom_bitmap(bmp + 1)
                        cad.lcd.write_custom_bitmap(bmp + 1)
                        steamState = 0

                lock.release()
                t = threading.Timer(max(0.2,0.2 * (timeFactor/2)), SteamThread)
                t.daemon = True
                t.start()

# Assess the age of the last brew every 10 secs. 
def AssessAge():
	global timeFactor
	global lastTime

	timeDiff = datetime.now().replace(tzinfo=to_zone) - lastTime
	timeFactor = max(min(90, timeDiff.seconds/60), 1)

	print("Old factor: " + str(timeFactor))
        t = threading.Timer(10, AssessAge)
        t.daemon = True
        t.start()

# Flash a message when a new jug is brewed
def FlashMessage(message):
	lock.acquire()
	cad.lcd.clear()
	
	# Draw the coffee cup
	cad.lcd.set_cursor(0,1)
	cad.lcd.write_custom_bitmap(0)
	cad.lcd.write_custom_bitmap(1)

	cad.lcd.set_cursor(5,0)
	cad.lcd.write("Last Brew:")
	cad.lcd.set_cursor(5,1)
	cad.lcd.write(message)

	lock.release()

	# Flash the screen by turning the backlight on/off
	count = 0
	while count < 5:
		cad.lcd.backlight_off()
		sleep(0.5)
		cad.lcd.backlight_on()
		sleep(0.5)
		count += 1

# Listen to the twitter stream, flashing each new message
class StreamWatcherListener(tweepy.StreamListener):
	def on_status(self, status):
		global lastTime
		print "== ", status.author.screen_name, status.created_at, status.source
		print ">> ", status.text

		tweepyTime = status.created_at.replace(tzinfo=from_zone)
		lastTime = tweepyTime.astimezone(to_zone)

		FlashMessage(lastTime.strftime('%H:%M'))
	def on_error(self, status_code):
		print "ERROR STATUS CODE: " + str(status_code)
		FlashMessage("ERROR: " + str(status_code))
		if status_code == 420:
			#returning False in on_data disconnects the stream
			return False

auth = tweepy.OAuthHandler(consumerKey, consumerSecret)
auth.set_access_token(accessToken, accessTokenSecret)
api = tweepy.API(auth)

thisUser = api.get_user("OLCoffeeTime")
timeline = api.user_timeline(screen_name=thisUser.screen_name, count=1)

listener = StreamWatcherListener()

# Get the last coffee brewed on startup
for tweet in timeline:
	listener.on_status(tweet)

AssessAge()
SteamThread()

stream = tweepy.Stream(auth=auth, listener=listener, timeout=None)
stream.filter(follow=[str(thisUser.id)])
