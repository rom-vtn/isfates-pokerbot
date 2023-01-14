#This file runs all tests for the pokerbot library

import pokerbot as pb

#TODO implement tests for all math functions (that is, non-UI functions that return something) in the program
#Maybe put tests in another file?
#Tests working: card comparisons, poker hand scores
#Tests to do: PokerCalculator.assignRandmCards

def testCardComparison():
    try:
        deck = pb.Card.getDeck(None) #Get 52 card deck
        deck2 = pb.Card.getDeck(None) #Same deck but different objects
        for i in range(len(deck)): #Check that they're all equal to eachother
            assert deck[i] == deck2[i]
            for j in range(i):
                assert deck[i] != deck[j]
        return True #All tests have passed
    except AssertionError:
        return False #At least one assertion failed

def testPokerScores():
    pokerHands = [
        [pb.Card("H", 14), pb.Card("H", 13), pb.Card("H", 12), pb.Card("H", 11), pb.Card("H", 10)], #High Straight Flush
        [pb.Card("H",2),pb.Card("H",3),pb.Card("H",4),pb.Card("H",5),pb.Card("H",6)],#Low straight flush
        [pb.Card("H", 14),pb.Card("S", 14),pb.Card("C", 14),pb.Card("D", 14),pb.Card("D", 13)], #High 4-kind
        [pb.Card("H",2),pb.Card("S",2),pb.Card("C",2),pb.Card("D",2),pb.Card("H",14)],#Low 4-kind, high kicker
        [pb.Card("H",2),pb.Card("S",2),pb.Card("C",2),pb.Card("D",2),pb.Card("H",5)],#Same 4-kind, low kicker
        [pb.Card("H",14),pb.Card("S",14),pb.Card("C",14),pb.Card("D",10),pb.Card("C",10)], #High full house
        [pb.Card("H",2),pb.Card("S",2),pb.Card("C",2),pb.Card("H",14),pb.Card("H",14)],#Low full house, high kicker
        [pb.Card("H",2),pb.Card("S",2),pb.Card("C",2),pb.Card("H",3),pb.Card("H",3)],#Same full house, low kicker
        [pb.Card("S",2),pb.Card("S",4),pb.Card("S",9),pb.Card("S",11),pb.Card("S",14)], #Flush
        [pb.Card("S",10), pb.Card("H",11), pb.Card("S",12), pb.Card("C",13), pb.Card("D",14)], #High straight
        [pb.Card("S",2), pb.Card("H",3), pb.Card("S",4), pb.Card("C",5), pb.Card("D",6)], #Low Straight
        [pb.Card("S",2),pb.Card("H",2),pb.Card("D",2),pb.Card("H",9),pb.Card("C",5)], #Low 3-kind, high kickers
        [pb.Card("S",2),pb.Card("H",2),pb.Card("D",2),pb.Card("H",6),pb.Card("C",3)], #Same 3-kind, lower kickers
        [pb.Card("S",3),pb.Card("H",3),pb.Card("D",9),pb.Card("H",9),pb.Card("C",11)], #Double pair, low high pair
        [pb.Card("S",3),pb.Card("H",3),pb.Card("D",7),pb.Card("H",7),pb.Card("C",11)],#Same double pair, lower high pair
        [pb.Card("S",2),pb.Card("H",2),pb.Card("D",7),pb.Card("H",7),pb.Card("C",11)],#Same as previous but lower low pair
        [pb.Card("S",2),pb.Card("H",2),pb.Card("D",7),pb.Card("H",7),pb.Card("C",10)],#Same as previous but lower kicker
        [pb.Card("S",2),pb.Card("H",2),pb.Card("D",9),pb.Card("H",10),pb.Card("C",5)] #Low pair
    ]
    
    scores = [pb.PokerCalculator.getScore(None, hand) for hand in pokerHands]
    decreasing = [scores[i+1] < scores[i] for i in range(len(scores)-1)]
    return all(decreasing)

def testCalculatorAssignment():

    hasSameElements = lambda l1, l2: len(l1) == len(l2) and all([element in l2 for element in l1]) and all([element in l1 for element in l2])

    calc = pb.PokerCalculator(2, [pb.Card("S", 2), pb.Card("C", 3)]) #Will not be assigned
    copy = calc.copy()
    copy.assignRandomCards()

    return (calc is not copy) and (calc.otherPlayerCount == copy.otherPlayerCount) and hasSameElements(calc.playerDeck, copy.playerDeck) and not calc.tableCards and len(copy.tableCards) == 5 and not calc.otherPlayerDecks and len(copy.otherPlayerDecks) == 2 and len(copy.otherPlayerDecks[0]) == 2 

def runAllTests():
    for func in [testPokerScores, testCardComparison, testCalculatorAssignment]: #TODO: add all functions
        print(func.__name__, func())

if __name__ == "__main__":
    runAllTests()