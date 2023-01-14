import telebot #pyTelegramBotAPI
import random
import datetime #Get timestamps for logs
#import threading #No need to use our own threads, telebot is synchronous, and uses threading (takes care of it for us) 

class PokerBotException(Exception):
    """Default class for pokerbot exceptions, does nothing."""
    pass

class PokerBot():
    """Represents a Telegram poker bot."""
    def __init__(self, token: str, channelId=None)->None:
        """Initializes poker bot with the given token. Sends error/maintenance messages to channelId.
        Note: the bot has to be an admin member of the logging group given"""
        self.token = token
        self.channelId = channelId
        self.sessions = []
        self.bot = telebot.TeleBot(token)
        self.requestId = 0

        @self.bot.message_handler(commands=["help"])
        def helpMessageHandler(message)->None:
            self.bot.reply_to(message, "Hi! I'm a bot designed to help you get better at poker by informing you of your winning chances given the game state you gice me. Try me out using /start !")

        @self.bot.message_handler(commands=["start"])
        def startSession(message)->None:
            """Default /start command message handler. Creates new Session() object and calls its start() method."""
            try:
                self.requestId += 1
                session = Session(self.requestId, message, self)
                self.sessions.append(session)
                session.start()
            except Exception as e:
                self.logMessage("Got exception while running /start command: "+repr(e))
        

        @self.bot.callback_query_handler(func=lambda call: True)
        def botCallbackHandler(call)->None:
            """Default bot callback handler. Gives call and call content (without session ID) to matching session's callbackHandler.
            If no session matches, raises a PokerBotException and sends a message to callback sender."""
            try:
                sessionId, data = call.data.split("-", 1)
                session = None
                for s in self.sessions:
                    if s.idStr == sessionId:
                        session = s
                        break
                if session is None:
                    self.bot.send_message(call.from_user.id, "Error: given ID doesn't match any known sessions")
                    raise PokerBotException("Given ID doesn't match any known sessions")
                session.callbackHandler(call, data)
            except Exception as e:
                self.logMessage("Got exception while handling callback: "+repr(e))

    def start(self)->None:
        """Sends a startup message to logging group (if given), then starts the Telegram bot using telebot.TeleBot.infinity_polling()"""
        print(" ---- Starting bot ---- ")
        self.logMessage("Pokerbot has started!")
        self.bot.infinity_polling()
    
    def logMessage(self, text:str, sendToChat:bool=True)->None:
        """Logs entry containing text into logs to get better idea of how it works. sendToChat defines if message should be sent to chat or not."""
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        messageText = "[{}] {}".format(timestamp, text)
        if self.channelId is not None and sendToChat:
            self.bot.send_message(self.channelId, messageText)
        print(messageText)
        #TODO: Maybe import a logging library and call it too?

class Session():
    """Session storing a user interaction, game state and action stack."""
    def __init__(self, id: int, firstMessage: telebot.types.Message, parent: PokerBot):
        """Initialises session's identifying data and relationship with its parent PokerBot instance, as well as the game state and behavior parameters."""
        #Set identifying data
        self.id = id
        self.idStr = str(id)
        self.firstMessage = firstMessage
        self.parent = parent
        self.currentBotMessage = None
        
        #Set working parameters
        self.actionStack = []
        self.dataStack = []

        self.playerCount = None #NOTE: represents the number of opponents, doesn't include the user player
        self.playerDeck = []
        self.tableCards = []
        self.fullDeck = Card.getDeck(None) #Call method without actually creating a Card object
    
    def start(self)->None:
        """Initialises actionStack and sends 1st message asking for opponent count."""
        self.actionStack = ["mainMenuLoop","loadCalculator","getPlayerDeckCard", "getPlayerDeckCard", "setPlayerCount"]
        if self.currentBotMessage is not None: self.parent.bot.delete_message(chat_id=self.currentBotMessage.chat.id, message_id=self.currentBotMessage.id)
        markup = telebot.types.InlineKeyboardMarkup()
        for i in range(1,6): #1 to 5 other players, might change later
            markup.add(telebot.types.InlineKeyboardButton(str(i), callback_data=self.idStr+"-setPlayerCount-"+str(i))) 
        self.currentBotMessage = self.parent.bot.reply_to(self.firstMessage, "Before inputting your cards, how many other players are there?", reply_markup=markup)
    
    def callbackHandler(self, call: telebot.types.CallbackQuery, inputData: str)->None:
        """Recursively handles user input relative to session, either by itself or by calling specific event handlers. See documentation for more details."""
        #NOTE: all exceptions are normally handled by caller, no need to catch exceptions.
        if call.from_user.id != self.firstMessage.from_user.id:
            self.parent.bot.send_message(call.from_user.id, "Error: you're not allowed to edit that session!")
            raise PokerBotException("Callback user different from session creator!")
        #Check the type of callback and dispatch accordingly
        action, data = inputData.split("-", 1)
        assert self.actionStack #Assert action stack not empty (this should never raise an exception anyway)
        self.actionStack, toPerform = self.actionStack[:-1], self.actionStack[-1]
        transformTable = {"getPlayerDeckCard": ["setPlayerDeckCard","getCard"], "getTableCard": ["setTableCard","getCard"], "getCard":["setValue","setSuite"], "mainMenuLoop":["mainMenuLoop","mainMenuOnce"]}
        while toPerform in transformTable: #Transform into elementary operations
            self.actionStack += transformTable[toPerform]
            self.actionStack, toPerform = self.actionStack[:-1], self.actionStack[-1]
        #Then run elementary operation on "top" of stack (that is, end of list)
        #If elementary operation requires no user input, do it and call ourselves again to do next step
        #Then immediately return to not execute anything apart from calling self again (to avoid side effects from current iteraction)
        if toPerform == "setPlayerDeckCard":
            self.setPlayerDeckCardHandler(data)
            self.callbackHandler(call, inputData)
            return
        elif toPerform == "setTableCard":
            self.setTableCardHandler(data)
            self.callbackHandler(call, inputData)
            return
        elif toPerform == "loadCalculator":
            self.loadCalculatorHandler(data)
            self.callbackHandler(call, inputData)
            return
        #For other operations, check if user callback input matches expected format
        #NOTE: this will break if we do 2 identical elementary operations in a row (which should never happen anyway), be careful when managing stack
        if action != toPerform:
            #If it doesn't match, show the corresponding menu
            if toPerform == "setPlayerCount":
                self.start() #Displays player count selection menu
            elif toPerform == "setSuite":
                self.showSuiteSelect()
            elif toPerform == "setValue":
                self.showValueSelect()
            elif toPerform == "mainMenuOnce":
                self.showMainMenu()
            #Put back the action to be handled on top of stack, since it hasn't been handled yet
            self.actionStack.append(toPerform)
        else:
            #If it does match, save user data status and call self again
            if toPerform == "setPlayerCount":
                self.playerCountHandler(data)
            elif toPerform == "setSuite":
                self.setSuiteHandler(data)
            elif toPerform == "setValue":
                self.setValueHandler(data)
            elif toPerform == "mainMenuOnce":
                self.mainMenuOnceHandler(data)
                if data == "quit": return #Don't do recursion if session just got removed, prevents exceptions
            #Call ourselves again
            #Since there aren't any 2 identical elementary actions in a row (at least I hope future me will be wise enough to make sure this never happens), the next action will be different and will display a menu
            self.callbackHandler(call, inputData)

    def mainMenuOnceHandler(self, data:str)->None:
        """Handles user input from main menu"""
        if data == "reveal":
            #We shouldn't get this after 5 cards are on the table (option should be removed from menu)
            #If user ever does this, an exception might occur, but it won't freeze the bot
            #I'm not gonna bother making a solution for people messing with the bot
            self.actionStack.append("getTableCard")
        elif data == "retry":
            self.parent.bot.reply_to(self.firstMessage, "Restarting session...")
            self.actionStack = ["mainMenuLoop","loadCalculator","getPlayerDeckCard", "getPlayerDeckCard", "setPlayerCount"]
            self.dataStack = []
            self.playerCount = None
            self.playerDeck = []
            self.tableCards = []
            self.fullDeck = Card.getDeck(None)
        elif data == "quit":
            self.parent.bot.reply_to(self.firstMessage, "Session ended successfully!")
            self.parent.bot.delete_message(chat_id=self.currentBotMessage.chat.id, message_id=self.currentBotMessage.id)
            self.parent.sessions.remove(self) #We prevent exceptions when leaving by having specific return in callbackHandler()
        elif data == "replay":
            """Difference between replay and retry is that retry asks for all parameters and resets everything, while replay just clears decks and table and allows to remember gone cards"""
            #Proper card count has been ensured by menu card counting
            self.actionStack = ["mainMenuLoop","loadCalculator","getPlayerDeckCard", "getPlayerDeckCard"]
            self.playerDeck = []
            self.tableCards = []
            self.calculator = None

    def setTableCardHandler(self, data:str)->None:
        """Handles internal setTableCard operation: pops 2 values off of dataStack, adds corresponding card to table and updates full deck."""
        self.dataStack, suite, value = self.dataStack[:-2], self.dataStack[-2], self.dataStack[-1]
        card = Card(suite, int(value))
        self.tableCards.append(card) #NOTE: not the same list object as self.calculator.tableCards
        self.calculator.updateState(self.playerCount, [card]) #Keep player count, add only the card we popped from the stack
        self.fullDeck.remove(card)

    def showSuiteSelect(self)->None:
        """Shows the card suite selection menu."""
        #Check that cards of suites exist before giving option to user
        suites = {card.suite for card in self.fullDeck}
        markup = telebot.types.InlineKeyboardMarkup() #♠, ♥, ♦, ♣.
        if "S" in suites: markup.add(telebot.types.InlineKeyboardButton("Spades ♠", callback_data=self.idStr+"-setSuite-S"))
        if "D" in suites: markup.add(telebot.types.InlineKeyboardButton("Diamonds ♦", callback_data=self.idStr+"-setSuite-D"))
        if "H" in suites: markup.add(telebot.types.InlineKeyboardButton("Hearts ♥", callback_data=self.idStr+"-setSuite-H"))
        if "C" in suites: markup.add(telebot.types.InlineKeyboardButton("Clubs ♣", callback_data=self.idStr+"-setSuite-C"))
        #self.parent.bot.reply_to(self.firstMessage, "Select card suite", reply_markup=markup)
        self.parent.bot.edit_message_text("Select card suite", reply_markup=markup, chat_id=self.currentBotMessage.chat.id, message_id=self.currentBotMessage.id)
    
    def showValueSelect(self)->None:
        """Shows the card value selection value. Specifically omits values not in full deck to prevent cards being picked twice."""
        suite = self.dataStack[-1] #Should be defined by previous operation, no risk of error
        markup = telebot.types.InlineKeyboardMarkup(row_width=3)
        for i in range(2, 11):
            if Card(suite, i) in self.fullDeck:
                markup.add(telebot.types.InlineKeyboardButton(str(i), callback_data=self.idStr+"-setValue-"+str(i)))
        for letter, value in [("J",11),("Q",12),("K",13),("A",14)]:
            if Card(suite,value) in self.fullDeck:
                markup.add(telebot.types.InlineKeyboardButton(letter, callback_data=self.idStr+"-setValue-"+str(value)))
        #self.parent.bot.reply_to(self.firstMessage, "Select card value", reply_markup=markup)
        self.parent.bot.edit_message_text("Select card value", reply_markup=markup, chat_id=self.currentBotMessage.chat.id, message_id=self.currentBotMessage.id)

    def showMainMenu(self)->None:
        """Shows the game state's main menu with winning probability, current game state and action buttons as an inline keyboard."""
        #First, calculate the winning probability
        iterCount = 1000
        winningChance = self.calculator.getWinningChance(iterCount)
        #Then set up menu using known info
        inviteText = """Number of opponents: {}
        
Current winning chance : {}/{} ({}%)
        
Your cards: {} {}
        
Cards on table: {}
        
What do you want to do?""".format(self.playerCount, int(iterCount*winningChance), iterCount, winningChance*100, self.playerDeck[0].niceRepr(), self.playerDeck[1].niceRepr(), " ".join([card.niceRepr() for card in self.tableCards]))
        #Then make the menu
        markup = telebot.types.InlineKeyboardMarkup()
        if len(self.tableCards) < 5: #Don't show button if all table cards are assigned
            markup.add(telebot.types.InlineKeyboardButton("Reveal a card on the table ➕", callback_data=self.idStr+"-mainMenuOnce-reveal"))
        markup.add(telebot.types.InlineKeyboardButton("Retry game 🔄", callback_data=self.idStr+"-mainMenuOnce-retry"))
        if len(self.fullDeck) >= 7: #Make sure enough cards in the deck before offering a new game
            markup.add(telebot.types.InlineKeyboardButton("Replay a game (no cards thrown away) ♻️", callback_data=self.idStr+"-mainMenuOnce-replay"))
        markup.add(telebot.types.InlineKeyboardButton("Quit ❌", callback_data=self.idStr+"-mainMenuOnce-quit"))
        # self.parent.bot.reply_to(self.firstMessage, inviteText, reply_markup=markup)
        self.parent.bot.edit_message_text(inviteText, reply_markup=markup, chat_id=self.currentBotMessage.chat.id, message_id=self.currentBotMessage.id)

    def playerCountHandler(self, data:str)->None:
        """Updates the session's player count"""
        self.playerCount = int(data)
    
    def setSuiteHandler(self, data:str)->None:
        """Pushes the given card suite onto the dataStack."""
        self.dataStack.append(data)
    
    def setValueHandler(self, data:str)->None:
        """Pushes the given card value onto the dataStack"""
        self.dataStack.append(data)
    
    def setPlayerDeckCardHandler(self, data:str)->None:
        """Pops dataStack's top 2 values, adds corresponding card to player deck while removing it from full deck"""
        self.dataStack, suite, value = self.dataStack[:-2], self.dataStack[-2], self.dataStack[-1]
        card = Card(suite, int(value))
        self.playerDeck.append(card)
        self.fullDeck.remove(card)
    
    def loadCalculatorHandler(self, data:str)->None:
        """Initializes the PokerCalculator object with current game state"""
        self.calculator = PokerCalculator(self.playerCount, self.playerDeck, self.tableCards)

class Card():
    """Represents a playing card. Suite is in ["C", "S", "D", "H"],
        value is int. 2 <= value < 14."""
    def __init__(self, suite:str, value:int):
        """Assigns suite and value to card."""
        self.suite = suite
        self.value = value
    
    def __eq__(self, other)->bool:
        """Compares equality between itself and another Card instance."""
        return self.suite == other.suite and self.value == other.value
    
    def __repr__(self)->str:
        """Representation to show as command line text."""
        return self.suite+str(self.value)
    
    def niceRepr(self)->str: 
        """Representation to show nicely as user UI with symbols and correct card names."""
        suiteDict = {"D":"♦", "H":"♥", "S":"♠", "C":"♣"}
        if 2 <= self.value <= 10:
            value = str(self.value)
        else:
            value = {11:"J",12:"Q",13:"K",14:"A"}[self.value]
        return value+suiteDict[self.suite]
    
    def getDeck(self)->list:
        """Returns a full 52-card standard deck (list of Card objects)."""
        deck = []
        for suite in ["C", "H", "S", "D"]:
            for value in range(2, 15):
                deck.append(Card(suite, value))
        return deck


class PokerCalculator():
    """Class responsible for doing all math operations relative to game state.
    Assignment state (with bool attribute isAssigned) largely determines what is allowed and what isn't."""
    def __init__(self, otherPlayerCount: int, playerDeck: list, tableCards=[]):
        """Initializes PokerCalculator with game state."""
        self.otherPlayerCount = otherPlayerCount
        self.playerDeck = playerDeck
        self.tableCards = tableCards.copy() #Make sure it's a different object to avoid unexpected behavior
        self.otherPlayerDecks = []
        self.isAssigned = False
        
        #Generate a full standard deck, then remove all cards already displayed
        self.deck = Card.getDeck(None)
        
        for card in playerDeck+tableCards:
            #print("playerDeck, tableCards:", playerDeck, tableCards) #DEBUG
            #print("Current deck:", self.deck) #DEBUG
            self.deck.remove(card)
    
    def updateState(self, newOtherPlayerCount: int, newTableCards: list):
        """Updates internal state according to new information. Calculator must not already be assigned. newTableCards cannot contain any cards that are already used."""
        if self.isAssigned: raise PokerBotException("Can't update an assigned deck!")
        self.otherPlayerCount = newOtherPlayerCount
        self.tableCards += newTableCards
        try:
            for card in newTableCards:
                self.deck.remove(card)
        except:
            raise PokerBotException("newTableCards can't contain any already used cards.")

    
    def pickCard(self):
        """Picks a card from the deck, removes it from the deck and returns it."""
        try:
            card = random.choice(self.deck)
        except IndexError:
            raise PokerBotException("Can't pick a card from an empty deck!")
        self.deck.remove(card)
        return card

    def assignRandomCards(self):
        """Assigns the calculator by filling unknown spots with cards from deck and sets its state and data accordingly. Calculator must not already be assigned."""
        if self.isAssigned: raise PokerBotException("Calculator is already assigned!")
        self.isAssigned = True
        while len(self.tableCards) < 5:
            self.tableCards.append(self.pickCard())
        while len(self.otherPlayerDecks) < self.otherPlayerCount:
            self.otherPlayerDecks.append([self.pickCard(), self.pickCard()])

    def copy(self):
        """Returns a (deep) copy of the calculator; useful for making simulations. Calculator must not be assigned."""
        if not self.isAssigned:
            return PokerCalculator(self.otherPlayerCount, self.playerDeck.copy(), self.tableCards.copy())
        raise PokerBotException("Can't copy an assigned poker layout!")

    def getWinningChance(self, iterationCount=1000):
        """Calculates a simulation over iterationCount iterations and returns the proportion of won games as a float beteen 0 and 1. Calculator must not be assigned!"""
        if self.isAssigned:
            raise PokerBotException("Can't start analysis on already assigned decks!")
        wonGames = 0
        for _ in range(iterationCount):
            copy = self.copy()
            copy.assignRandomCards()
            if copy.isWinning():
                wonGames += 1
        return wonGames / iterationCount
    
    def isWinning(self):
        """Checks if the calculator represents a situation where the player is winning. Calculator must be assigned!"""
        if not self.isAssigned: raise PokerBotException("Deck must be assigned to check for player win.")
        playerScore = self.getScore(self.playerDeck+self.tableCards)
        otherPlayerScores = [self.getScore(deck+self.tableCards) for deck in self.otherPlayerDecks]

        bestOtherPlayerScore = max(otherPlayerScores)
        return playerScore > bestOtherPlayerScore

    def getScore(self, cards: list):
        """Calculates the score of a 5-or-more card poker hand recursively. Scores can be compared to check which hand is winning."""
        # print("getScore() called with:", cards) #DEBUG
        #Split into recursion if more than 5 cards
        if len(cards) > 5:
            scores = []
            for i in range(len(cards)-1):
                scores.append(self.getScore(cards[:i]+cards[i+1:]))
            return max(scores)
        if len(cards) < 5:
            raise PokerBotException("Can't get the score for a deck with less than 5 cards!")
        
        # print("Checking:", cards) #DEBUG

        #Check for flushes
        hasFlush = True
        for card in cards:
            if card.suite != cards[0].suite: hasFlush = False
        
        # if hasFlush: #DEBUG
        #    print("Got a flush!")
        # else:
        #    print("No flush found!")
        
        #Check for n-of-a-kind
        values = {}
        for card in cards:
            if card.value not in values:
                values[card.value] = 1
            else:
                values[card.value] += 1
        sameKinds = [(values[value], value) for value in values] #(count, type) tuples
        sameKinds.sort(reverse=True, key=lambda x: x[0]*16+x[1]) #count comes first, then type matters
        #Check for straights
        # print("sameKinds:", sameKinds) #DEBUG
        cards.sort(key=lambda card:card.value)
        hasStraight = None
        straightHigh = None
        if len(sameKinds) != 5: hasStraight = False
        if hasStraight is None:
            hasStraight = (cards[4].value-cards[0].value) == 4
            if hasStraight:
                straightHigh = max(cards, key=lambda card:card.value).value
            else: #Check special case of A-2-3-4-5
                hasStraight = (cards[3].value-cards[0].value == 3) and cards[1].value == 14
                if hasStraight:
                    straightHigh = 5 #5-high straight
        else:
            hasStraight = False
        
        # if hasStraight: #DEBUG
        #    print("Got a straight!")
        # else:
        #    print("No straight found!")
        
        #Then get score according to poker hand hierarchy
        
        score = 0
        attributes = []
        #Straight+Flush
        if hasFlush and hasStraight:
            attributes.append("{}-high straight flush".format(straightHigh))
            score += straightHigh
        score *= 16
        #4-kind
        try:
            if sameKinds[0][0] == 4:
                attributes.append("4-of a kind with {}".format(sameKinds[0][1]))
                score += sameKinds[0][1]
                score *= 16
                score += sameKinds[1][1]
                score *= 16
            else:
                raise IndexError #Do the x256 in a nonsensical-ish way
        except IndexError:
            score *= 256
        #3-kind + 2-kind
        try:
            if sameKinds[0][0] == 3 and sameKinds[1][0] == 2:
                attributes.append("Full house with {}+{}".format(sameKinds[0][1], sameKinds[1][1]))
                score += sameKinds[0][1]
                score *= 16
                score += sameKinds[1][1]
                score *= 16
            else:
                raise IndexError
        except IndexError:
            score *= 256
        #Flush
        if hasFlush:
            attributes.append("Flush with {}".format(cards[0].suite))
            score += 1
        score *= 16
        #Straight
        if hasStraight:
            attributes.append("{}-high straight".format(straightHigh))
            score += straightHigh
        score *= 16
        #3-kind
        if sameKinds[0][0] == 3:
            attributes.append("3-of a kind with {}".format(sameKinds[0][1]))
            score += sameKinds[0][1]
            score *= 16
            score += sameKinds[1][1]
            score *= 16
            score += sameKinds[-1][1] #If it's a 3-kind+pair it'll be handled without errors
            score *= 16
        else:
            score *= 4096
        
        
        #2x 2-kind
        try:
            if sameKinds[0][0] == 2 and sameKinds[1][0] == 2:
                maxVal = max(sameKinds[0][1], sameKinds[1][1])
                minVal = min(sameKinds[0][1], sameKinds[1][1])
                kicker = sameKinds[2][1]
                attributes.append("{}-high {}-low double pair".format(maxVal, minVal))
                #score += maxVal*4096 + minVal*256 + kicker*16
                score += maxVal
                score *= 16
                score += minVal
                score *= 16
                score += kicker
                score *= 16
            else:
                raise IndexError
        except IndexError:
            score *= 4096
        #2-kind
        if sameKinds[0][0] == 2:
            attributes.append("{}-high pair".format(sameKinds[0][1]))
            score += sameKinds[0][1]
        #Take raw card values into account (high cards)
        cards.sort(reverse=True, key=lambda card: card.value) #Sort from highest to lowest, then store individual card values
        for card in cards:
            score *= 16
            score += card.value
        
        # print(attributes) #DEBUG
        return score


if __name__ == "__main__":
    import sys
    if len(sys.argv) not in (2,3):
       print("Syntax: python \"{}\" <BOT_TOKEN> [DEBUG_CHANNEL_ID].".format(sys.argv[0]))
       exit(1) #Exit with error
    token = sys.argv[1]
    try:
        channelId = sys.argv[2]
    except IndexError:
        channelId = None
    if channelId is None:
        print("""Note: Pokerbot started without a debug channel.
Add the debug channel ID after your API token as an argument to get all exceptions and debug messages sent there.
NOTE: the bot has to be an admin of the given group (otherwise it's not allowed to send messages without prior interactions)""")
    pokerbot = PokerBot(token, channelId)
    pokerbot.start()