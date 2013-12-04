#!/usr/bin/env python

# Authors:
# George Darling
# Zack Eggleston
# Credits to Dr. Ralph Butler

# Last updated:
# 12/03/2013

# current notes. 
# 2. local two player have seperate controls on the keyboard - need to have game know if it is localmp vs network
# 2.5 local two player has no command line args, network multi waits for 2nd player
# 3. game interface with <space> to play, scores, text etc.
# 4. quiting does not play nice with multiplayer - that makes sense, but needs fixing.

# Ideas:
# sound?
# score in background
# changing angle of ball based on paddle movement and maybe location hitting on paddle.
# four player square board pong

# built off of project 4, credits to Dr. Butler for socket communication things
"""This is a multiplayer Pong game that works over LAN. 
Player1 runs with python pong.py <portnum> 
Player2 runs with python pong.py <hostname> <portnum> """

import sys
import threading
from time import sleep
import cPickle
import select
import socket
import Tkinter

# Global variables----------------------------------------------------------------------------------------

# Constants
canvasHeight = 480
canvasWidth  = 800
ballSize = 20
paddleHeight = 100
paddleWidth = 10
p1Initial = (2, canvasHeight/2 - paddleHeight/2)
p2Initial = (canvasWidth - paddleWidth + 2, canvasHeight/2 - paddleHeight/2)
ballInitial = (canvasWidth/2 - ballSize/2, canvasHeight/2 - ballSize/2)

# Actually just used internally in server
p1posx = p1Initial[0] 
p1posy = p1Initial[1]
p2posx = p2Initial[0]
p2posy = p2Initial[1]
bposx = ballInitial[0]
bposy = ballInitial[1]
bdx = 1 # how much for the ball to move each time
bdy = 1 
dx = 1 # how much to move paddle each time
dy = 1
Uisp = False # whether to move paddle or not
Disp = False  # "Down key is pressed"
msgLock = threading.Lock()
msgdict = {}

# Used between game and communications
UDkeyLock = threading.Lock() # get locks
UDpressed = 0 # for up and down arrow keys
Upispressed = False # on key press, set to true, on release set to false
Downispressed = False  # used between game and communications
p1Lock = threading.Lock()
p2Lock = threading.Lock()
p1move = p1Initial # coordinates that communication passes to game
p2move = p2Initial # x, y
bLock = threading.Lock()
bmove = ballInitial
localmp = False

sUprev = False # memory for communications
sDprev = False 

ignoreL = 0
ignoreR = 0
twoplayer = False # need to have two players to start the game
quit = False

# Helper functions---------------------------------------------------------------------------------------
def Send(mysocket, msg): # send the message. all of the silly length stuff is handled here.
	pickledMsg = cPickle.dumps(msg)
	mysocket.sendall( '%08d%s' % (len(pickledMsg),pickledMsg))
def Receive(mysocket):
	#msglength = mysocket.recv(8, socket.MSG_WAITALL) # receive the length of the message to follow
	msglength = mysocket.recv(8) # receive the length of the message to follow
	if not msglength: return {}
	# pickledMsg = mysocket.recv(int(msglength), socket.MSG_WAITALL) # receive msglength many characters 
	pickledMsg = mysocket.recv(int(msglength)) # receive msglength many characters S
	if not pickledMsg : return {}
	msg = cPickle.loads(pickledMsg)
	return msg

# Server and move-making------------------------------------------------------------------------------------------------------
def server():
	global twoplayer, quit, socketlist, msgdict
	def broadcast(msg):
		global socketlist # in theory there could be a problem here if socketlist were changed while trying to send.
		for s in socketlist[1:]: # send to all but the listening socket
			Send(s, msg)

	# do all the movement calculating here
	# Just in its own function so it is easier to read.
	# returns a dictionary saying where to move to
	def movement():
		# static variables for movement():
		global p1posx, p1posy, p2posx, p2posy, bposx, bposy, bdx, bdy, dx, dy
		global ignoreL, ignoreR, Uisp, Disp
		global p1moving, p1up, p2moving, p2up
		# global constants:
		global canvasHeight, canvasWidth, ballSize, paddleHeight, paddleWidth
		# interthread communication:
		global quit, msgdict
		p1posx = p1Initial[0] 
		p1posy = p1Initial[1] ###################
		p2posx = p2Initial[0]
		p2posy = p2Initial[1]
		bposx = ballInitial[0]
		bposy = ballInitial[1]
		p1moving = False; p1up = False; p2moving = False; p2up = False
		# make all the other static variables like these as well

		while(not quit):
			sleep(.001) # use a variable for the sleep time - smaller sleep time, faster ball.
			msgLock.acquire()
			d = msgdict
			msgdict = {}
			msgLock.release()

			# change in paddles
			if d:
				if(d["p"] == 1):
					if d["u"]:
						p1moving = True 
						p1up = True
					elif d["d"]:
						p1moving = True 
						p1up = False
					else:
						p1moving = False
				elif(d["p"] == 2):
					if d["u"]:
						p2moving = True 
						p2up = True
					elif d["d"]:
						p2moving = True 
						p2up = False
					else:
						p2moving = False
			# move paddles
			if p1moving:
				if p1up:
					p1posy -= dy # note that it seems backwards:P
				else: p1posy += dy 
				if p1posy > (canvasHeight-paddleHeight): p1posy = canvasHeight - paddleHeight
				if p1posy < 0: p1posy = 0
			if p2moving:
				if p2up:
					p2posy -= dy 
				else: p2posy += dy 
				if p2posy > (canvasHeight-paddleHeight): p2posy = canvasHeight - paddleHeight
				if p2posy < 0: p2posy = 0

			# move ball
			bposx += bdx
			if bposx > canvasWidth - ballSize: # comment
				bposx = canvasWidth - ballSize
				bdx = -bdx
			if bposx < 0:
				bposx = 0
				bdx = -bdx # comment
			bposy += bdy
			if bposy > canvasHeight - ballSize:
				bposy = canvasHeight - ballSize
				bdy = -bdy
			if bposy < 0:
				bposy = 0
				bdy = -bdy

			# Ball is touching left paddle
			if not ignoreL:
				if bposy + ballSize/2 >= p1posy and bposy + ballSize/2 <= p1posy + paddleHeight \
					and bposx > 0 and bposx <= paddleWidth+2:
					bdx = -bdx
					ignoreL = 20 # don't go back into this code for 20 times. What sometimes happens is the 
					# ball gets "stuck" in the paddle since it is a region, not just a line
			else:
				ignoreL -= 1
			# Ball is touching right paddle
			if not ignoreR:
				if bposy + ballSize/2 >= p2posy and bposy + ballSize/2 <= p2posy + paddleHeight \
					and bposx < canvasWidth and bposx >= canvasWidth - paddleWidth-2:
					bdx = -bdx
					ignoreR = 20 # don't go back into this code for 20 times. What sometimes happens is the 
					# ball gets "stuck" in the paddle since it is a region, not just a line
			else:
				ignoreR -= 1

			### Winning / losing case ###########################################################################
			if bposx > canvasWidth - ballSize/2:
				quit = True
			if bposx < 0:
				quit = True

			broadcast({"bm" : (bposx, bposy) , "p1m" : (p1posx, p1posy) , "p2m" : (p2posx, p2posy)})
			#return {"bm" : (bposx, bposy) , "p1m" : (p1posx, p1posy) , "p2m" : (p2posx, p2posy)}

	listeningSocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
	listeningSocket.bind(('', int(sys.argv[1]))) # Host (any?),  Use port given in command line
	listeningSocket.listen(5) # start listening for incoming connections, up to 5 of them.
	listeningPort = listeningSocket.getsockname()[1] # get information about the socket (specifically the port number)
	print 'Server is istening on socket: ', listeningSocket
	print 'Port: ', listeningPort 

	socketlist = [listeningSocket] # add the listening socket to a list of sockets to manage.
	moveT = threading.Thread(target = movement)
	moveT.start()

	# need to manage the socket that can manage incoming connections, and any sockets that are being talked on.
	while True:
	#for i1 in xrange(0,100):
		if quit: break
		(readingsockets, writingsockets, something) = select.select(socketlist,[],[],5) # select system call on the sockets that are being managed
		# reading, unused, unused, 30 second timeout
		for currentsocket in readingsockets: # go through each socket that is ready to be read from
			if currentsocket == listeningSocket: # manage the listening socket - there is an incoming request
				(talkingSocket, address) = listeningSocket.accept() # accept the incoming request
				socketlist.append(talkingSocket) # the request was given another socket to talk on and is added to the list to listen to
				if len(socketlist) > 2: twoplayer = True
				# we can assume that the first socket in the list is the server, second is player 1, third is player 2.

			else: # a socket that is "in communication" and connected with client.
				receivedmsg = Receive(currentsocket) # grab the message
				if not receivedmsg: # no message, remove the socket
					socketlist.remove(currentsocket) # no message, remove the socket
					currentsocket.close()
					if len(socketlist) < 2 : sys.exit(0) # quit everything if there are no players
				else: 
					msgLock.acquire()
					msgdict = receivedmsg
					msgLock.release()
					#sendmove = movement(receivedmsg)
					#broadcast(socketlist, sendmove)
					#elif(receivedmsg["p"] == 2):
					#	p2posx += receivedmsg["keys"]
					#	broadcast(socketlist, {"p2m" : p2posx})
	moveT.join()


# Client communications-------------------------------------------------------------------------------------------------------
def communication(portnum, player):
	def fromserver(mysock, player):
		# interthread communication to game
		global p1move, p2move, bmove, quit
		while(True): #just loop and receive
			if quit: break
			msg = Receive(mysock)
			if "bm" in msg.keys():
				bLock.acquire()
				bmove = msg["bm"]
				bLock.release()
			if "p1m" in msg.keys():
				p1Lock.acquire() #lock
				p1move = msg["p1m"]
				p1Lock.release() #unlock
			if "p2m" in msg.keys():
				p2Lock.acquire() # lock
				p2move = msg["p2m"]
				p2Lock.release() # unlock
			# retreive message from server
				# set the global domove tupple

	def toserver(mysock, player):
		# interthread communication from game
		global Upispressed, Downispressed, quit, sUprev, sDprev
		while(True): # just loop and send to server at some interval
			if quit: break
			sleep(0.001) # 1 ms.

			UDkeyLock.acquire()
			sendUp = Upispressed
			sendDown = Downispressed
			UDkeyLock.release()

			if sendUp != sUprev or sendDown != sDprev: # only send if there is a change in the input
				Send(mysock, {"p" : player, "u" : sendUp, "d" : sendDown}) # I think might get lower latency just sending an char, not a boolean
			sUprev = sendUp
			sDprev = sendDown

	sleep(.5) # in case server takes time to load?
	print 'Starting client.'
	mysocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM) # I can haz internet socket plz?
	mysocket.connect(("localhost",int(portnum)))  # note the tuple
	mysocket.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1) # no delay in sending data
	# connect to: computer name, socket
	# split into threads, one for sending, one for receiving from server
	commthreads = []
	commthreads.append(threading.Thread(target = fromserver, args = (mysocket,player)))
	commthreads.append(threading.Thread(target = toserver, args = (mysocket, player)))
	for s in commthreads: s.start()
	for v in commthreads: v.join()


# Graphics and game----------------------------------------------------------------------------------------------------------
def game(player):
	# interthread communication about the program:
	global twoplayer, quit
	# global constants:
	global canvasHeight, canvasWidth, ballSize, paddleWidth, paddleHeight
	# interthread communication about the game:
	global p1move, p2move

	#try:
		## If you separate the Press and Release events, you can remember when a press occurs
	##    and continue to move that direction until the corresponding release occurs.
	## Thus, by remembering both a Down and Right, you can move both down and right (diagonally).
	# canvas.bind_all('<KeyPress-Up>',move) # note that key has been pressed, continue its action until it is let up
	# canvas.bind_all('<KeyRelease-Up>',move) # this allows for multiple keys to be pressed.
	#def move(event):

	def UpPressed(event):
		global Upispressed
		UDkeyLock.acquire() #lock # question - will these locks really slow things down?
		Upispressed = True
		UDkeyLock.release() # unlock
	def UpReleased(event):
		global Upispressed
		UDkeyLock.acquire() #lock
		Upispressed = False
		UDkeyLock.release() # unlock
	def DownPressed(event):
		global Downispressed
		UDkeyLock.acquire() #lock # question - will these locks really slow things down?
		Downispressed = True
		UDkeyLock.release() # unlock
	def DownReleased(event):
		global Downispressed
		UDkeyLock.acquire() #lock
		Downispressed = False
		UDkeyLock.release() # unlock

	def update(): # schedules itself to run every 10 ms. might be better to have in own thread
		global p1move, p2move, bmove
		global canvasHeight, canvasWidth, ballSize
		global twoplayer
		canvas.after(10, update) # schedule self to update frequently
		# get the positions from communications which gets them from the server
		bLock.acquire()
		bx = bmove[0]
		by = bmove[1]
		bLock.release()

		p1Lock.acquire() #lock
		p1x = p1move[0] # just here in the main loop
		p1y = p1move[1]
		p1Lock.release() # unlock

		p2Lock.acquire() #lock
		p2x = p2move[0]
		p2y = p2move[1]
		p2Lock.release() #unlock
		# now update graphics:
		canvas.coords(ball,bx,by,bx+ballSize,by+ballSize)
		canvas.coords(rect1,p1x,p1y,p1x+paddleWidth,p1y+paddleHeight) # update the screen
		if twoplayer:
			canvas.coords(rect2,p2x,p2y,p2x+paddleWidth,p2y+paddleHeight) # update the screen

	root = Tkinter.Tk()
	canvas = Tkinter.Canvas(root,bg="white",height=canvasHeight,width=canvasWidth)
	canvas.pack()
	canvas.bind_all('<KeyPress-Up>',UpPressed)
	canvas.bind_all('<KeyRelease-Up>',UpReleased)
	canvas.bind_all('<KeyPress-Down>',DownPressed)
	canvas.bind_all('<KeyRelease-Down>',DownReleased)

	line = canvas.create_line(canvasWidth/2, 0, canvasWidth/2, canvasHeight, width=4, fill="gray", dash=(4, 8))
	ball = canvas.create_oval(ballInitial[0],ballInitial[1],ballInitial[0]+ballSize,ballInitial[1]+ballSize,width=2,fill="black")
	rect1 = canvas.create_rectangle(p1Initial[0],p1Initial[1],p1Initial[0]+paddleWidth,p1Initial[1]+paddleHeight,width=2,fill="red")
	rect2 = canvas.create_rectangle(p2Initial[0],p2Initial[1],p2Initial[0]+paddleWidth,p2Initial[1]+paddleHeight,width=2,fill="green")

	root.attributes("-topmost", True)   # raise above other windows
	update()
	root.mainloop()
	#except:
	#	print "Exception in game thread. "
	quit = True

# Main function---------------------------------------------------------------------------------------------------------------
if len(sys.argv) == 1: # local multiplayer
	localmp = True
	# server
	serverT = threading.Thread(target = server)
	serverT.start()    
	# player 1
	gameT1 = threading.Thread(target = game, args = (1,))
	commT1 = threading.Thread(target = communication, args = (56789, 1)) # hardcode portnum
	gameT1.start()
	commT1.start()
	# player 2
	gameT2 = threading.Thread(target = game, args = (2,))
	commT2 = threading.Thread(target = communication, args = (56789, 2))
	gameT2.start()
	commT2.start()
	# join
	gameT1.join()
	gameT2.join()
	commT1.join()
	commT2.join()
	serverT.join()
	
elif len(sys.argv) == 2:
	serverT = threading.Thread(target = server)
	gameT = threading.Thread(target = game, args = (player,))
	commT = threading.Thread(target = communication, args = (int(sys.argv[1]), 1))
	serverT.start()
	gameT.start()
	commT.start()

	gameT.join()
	serverT.join()
	commT.join()
	sys.exit(0)

elif len(sys.argv) == 3:
	twoplayer = True
	gameT = threading.Thread(target = game, args = (player,))
	commT = threading.Thread(target = communication, args = (int(sys.argv[1]), 2))
	gameT.start()
	commT.start()

	gameT.join()
	commT.join()
	sys.exit(0)

else: "Usage: for player 1, p4.py <portnum>, for player 2, p4.py <hostname> <portnum>"
