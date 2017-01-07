import random

class Compliment():
	def __init__(self):
		self.male_compliments = ['more handsome', 'uglier', 'taller', 'shorter', 'sexier', 'good looking', 'chubbier', 'more funny-looking', 'older', 'younger']
		self.female_compliments = ['prettier', 'more elegant', 'uglier', 'sexier', 'younger', 'older', 'chubbier', 'thinner']

def getRandomCompliment(sex):
	if sex == 'male':
		return random.choice(male_compliments)
	else:
		return random.choice(femaale_compliments)
