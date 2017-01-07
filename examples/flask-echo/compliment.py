import random

male_compliments = ['more handsome', 'uglier', 'taller', 'shorter', 'sexier', 'good looking', 'chubbier', 'more funny-looking', 'older', 'younger']
female_compliments = ['prettier', 'more elegant', 'uglier', 'sexier', 'younger', 'older', 'chubbier', 'thinner']

def getRandomCompliment(sex):
	if sex == 'male':
		return random.choice(male_compliments)
	elif sex == 'female':
		return random.choice(femaale_compliments)
