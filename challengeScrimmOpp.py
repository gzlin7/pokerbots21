'''
Repeatedly challenge an opponent to collect data
Use ethically (at your own risk)
'''

import requests
import time

SESSION_COOKIE_STR = 'session=example_session_cookie'

TEAM_ID_STR = '58'

headers = {
    'authority': 'scrimmage.pokerbots.org',
    'cache-control': 'max-age=0',
    'sec-ch-ua': '"Chromium";v="88", "Google Chrome";v="88", ";Not A Brand";v="99"',
    'sec-ch-ua-mobile': '?0',
    'origin': 'https://scrimmage.pokerbots.org',
    'upgrade-insecure-requests': '1',
    'dnt': '1',
    'content-type': 'application/x-www-form-urlencoded',
    'user-agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 11_1_0) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/88.0.4324.96 Safari/537.36',
    'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.9',
    'sec-fetch-site': 'same-origin',
    'sec-fetch-mode': 'navigate',
    'sec-fetch-user': '?1',
    'sec-fetch-dest': 'document',
    'referer': 'https://scrimmage.pokerbots.org/',
    'accept-language': 'en-US,en;q=0.9',
    'cookie': SESSION_COOKIE_STR,
}

data = {
  'team_id': TEAM_ID_STR
}

while True:

	for i in range(5):

		response = requests.post('https://scrimmage.pokerbots.org/challenge', headers=headers, data=data)

	time.sleep(60)
