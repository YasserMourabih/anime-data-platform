import requests
import json

# 1. Define API URL
API_URL = "https://graphql.anilist.co"

# 2. Define GraphQL query
# We use a multi-line string (triple quotes) for readability.
QUERY = '''
query ($page: Int, $perPage: Int) {
  Page (page: $page, perPage: $perPage) {
    media (type: ANIME, sort: POPULARITY_DESC) {
      id
      title {
        romaji
        english
      }
      averageScore
    }
  }
}
'''

# 3. Define the variables for our query
# It is good practice to separate the query structure from the values.
variables = {
    'page': 1,
    'perPage': 10
}

# 4. Make the HTTP POST request
# The GraphQL API expects a POST request with a JSON containing 'query' and 'variables'.
response = requests.post(API_URL, json={'query': QUERY, 'variables': variables})

# 5. Check if the request was successful (Code 200 OK)
if response.status_code == 200:
    data = response.json()
    # Navigate through the JSON response to reach the list of anime
    # The structure of the response follows the structure of the request.
    anime_list = data['data']['Page']['media']
    print(f"✅ Success! Here are {len(anime_list)} anime :\n")
    # Sometimes the English title is missing (None), so we use the romaji by default.
    for anime in anime_list:    
        titre = anime['title']['english'] or anime['title']['romaji']
        score = anime['averageScore']
        print(f"- {titre} (Score moyen : {score}/100)")
else:
    print(f"❌ Erreur lors de la requête : {response.status_code}")
    print(response.text)